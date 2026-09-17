#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

#include "LUCIDA_Depth.h"
#include "LUCIDA_DepthParamMapping.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <mutex>
#include <sstream>

#include <ffgl/FFGLLib.h>
#include <ffgl/FFGLLog.h>
#include <ffglex/FFGLScopedSamplerActivation.h>
#include <ffglex/FFGLScopedShaderBinding.h>
#include <ffglex/FFGLScopedTextureBinding.h>

using namespace ffglqs;

namespace {

static CFFGLPluginInfo PluginInfo(
	PluginFactory<LUCIDA_DEPTH>,
	"LD02",
	"LUCIDA Depth",
	2,
	1,
	1,
	0,
	FF_EFFECT,
	"DepthGen monocular depth from the Resolume input texture.",
	"LUCIDA / DepthGen FFGL port");

constexpr char kFragmentShader[] = R"(
	uniform sampler2D depthTexture;

	float CctvHash(vec2 value)
	{
		return fract(sin(dot(value, vec2(12.9898, 78.233))) * 43758.5453);
	}

	float ElectricValueNoise(vec2 value)
	{
		vec2 cell = floor(value);
		vec2 local = fract(value);
		local = local * local * (3.0 - 2.0 * local);
		float a = CctvHash(cell);
		float b = CctvHash(cell + vec2(1.0, 0.0));
		float c = CctvHash(cell + vec2(0.0, 1.0));
		float d = CctvHash(cell + vec2(1.0, 1.0));
		return mix(mix(a, b, local.x), mix(c, d, local.x), local.y);
	}

	float ElectricFbm(vec2 value)
	{
		float sum = 0.0;
		float amplitude = 0.5;
		for (int octave = 0; octave < 3; ++octave)
		{
			sum += ElectricValueNoise(value) * amplitude;
			value = value * 2.03 + vec2(17.13, 9.71);
			amplitude *= 0.5;
		}
		return sum;
	}

	vec3 ThermalDepth(float value)
	{
		vec3 nearColor = vec3(1.0, 0.08, 0.02);
		vec3 midColor = vec3(1.0, 0.85, 0.02);
		vec3 farColor = vec3(0.02, 0.18, 1.0);
		return value < 0.5
			? mix(farColor, midColor, value * 2.0)
			: mix(midColor, nearColor, (value - 0.5) * 2.0);
	}

	float DepthEdge(vec2 uv)
	{
		uv = clamp(uv, vec2(0.001), vec2(0.999));
		float center = texture(depthTexture, uv).r;
		return clamp(length(vec2(dFdx(center), dFdy(center))) * EdgeGain, 0.0, 1.0);
	}

	float DepthGate(float depthValue)
	{
		if (DepthGateWidth >= 0.999) return 1.0;
		return 1.0 - smoothstep(0.0, max(DepthGateWidth, 0.001),
			abs(depthValue - EmissionDepth));
	}

	float AuraField(vec2 uv, vec2 texel)
	{
		float field = 0.0;
		for (int direction = 0; direction < 8; ++direction)
		{
			float angle = float(direction) * 0.7853981634;
			vec2 directionVector = vec2(cos(angle), sin(angle));
			for (int ring = 0; ring < 3; ++ring)
			{
				float radius = AuraRadius * (0.35 + float(ring) * 0.35);
				vec2 offset = directionVector * texel * radius;
				float edge = DepthEdge(uv + offset);
				float sampleDepth = texture(depthTexture, clamp(uv + offset, vec2(0.001), vec2(0.999))).r;
				float distanceFalloff = exp(-float(ring) * AuraFalloff * 0.8);
				field = max(field, edge * distanceFalloff * DepthGate(sampleDepth));
			}
		}
		return clamp(field, 0.0, 1.0);
	}

	vec2 LightningPoint(vec2 origin, vec2 direction, vec2 aspect, float t,
		float seed, float segmentLength, float branchAmount)
	{
		vec2 perpendicular = vec2(-direction.y, direction.x);
		float noiseScale = 2.5 + RayDensity * 0.12;
		float coarse = ElectricValueNoise(vec2(t * noiseScale + seed,
			time * (0.18 + RayFlicker * 0.28) + seed * 2.07));
		float fine = ElectricValueNoise(vec2(t * (noiseScale + 10.0) - seed * 1.41,
			-time * 0.31 + seed * 0.73));
		float stepJitter = CctvHash(vec2(floor(t * 12.0) + seed * 3.17, seed * 5.7 + 11.0));
		float microJitter = CctvHash(vec2(floor(t * 24.0) - seed * 1.9, seed * 2.3 + 19.0));
		float envelope = smoothstep(0.0, 0.08, t) * (1.0 - 0.22 * smoothstep(0.92, 1.0, t));
		float displacement = ((coarse * 2.0 - 1.0) * (0.018 + 0.100 * t) +
			(fine * 2.0 - 1.0) * (0.012 + 0.030 * t) +
			(stepJitter * 2.0 - 1.0) * (0.022 + 0.075 * t) +
			(microJitter * 2.0 - 1.0) * 0.012) * branchAmount * envelope;
		vec2 position = direction * (t * segmentLength) + perpendicular * displacement;
		return origin + position / aspect;
	}

	float LightningSegmentDistance(vec2 uv, vec2 aspect, vec2 p0, vec2 p1, out float along)
	{
		vec2 segment = (p1 - p0) * aspect;
		vec2 localUv = (uv - p0) * aspect;
		float segmentLengthSquared = max(dot(segment, segment), 0.000001);
		along = clamp(dot(localUv, segment) / segmentLengthSquared, 0.0, 1.0);
		return length(localUv - segment * along);
	}

	vec3 LightningBolt(vec2 uv, vec2 sourceSize, vec2 aspect, float currentDepth,
		vec2 origin, vec2 direction, float seed, float segmentLength)
	{
		float closestDistance = 1000000.0;
		vec2 closestPoint = origin;
		vec2 closestDirection = direction;
		float closestT = 0.0;
		const int trunkSegments = 8;
		for (int segmentIndex = 0; segmentIndex < trunkSegments; ++segmentIndex)
		{
			float t0 = float(segmentIndex) / float(trunkSegments);
			float t1 = float(segmentIndex + 1) / float(trunkSegments);
			vec2 p0 = LightningPoint(origin, direction, aspect, t0, seed,
				segmentLength, RayBranching);
			vec2 p1 = LightningPoint(origin, direction, aspect, t1, seed,
				segmentLength, RayBranching);
			float along = 0.0;
			float distanceToBolt = LightningSegmentDistance(uv, aspect, p0, p1, along);
			if (distanceToBolt < closestDistance)
			{
				closestDistance = distanceToBolt;
				closestPoint = mix(p0, p1, along);
				closestT = mix(t0, t1, along);
			}
		}

		vec2 perpendicular = vec2(-direction.y, direction.x);
		for (int branchIndex = 0; branchIndex < 2; ++branchIndex)
		{
			float branchSeed = seed + float(branchIndex) * 43.7;
			float forkActive = step(0.42, CctvHash(vec2(branchSeed, 31.7))) *
				step(0.001, RayBranching);
			float forkT = 0.24 + 0.48 * CctvHash(vec2(branchSeed, 47.9));
			vec2 forkPoint = LightningPoint(origin, direction, aspect, forkT, branchSeed + 4.3,
				segmentLength, RayBranching);
			float forkSign = CctvHash(vec2(branchSeed, 59.3)) < 0.5 ? -1.0 : 1.0;
			vec2 forkDirection = normalize(direction + perpendicular * forkSign *
				(0.42 + RayBranching * 0.95));
			float forkLength = segmentLength * (0.30 + 0.34 * RayBranching) *
				(0.78 + 0.44 * CctvHash(vec2(branchSeed, 73.1)));
			const int forkSegments = 4;
			for (int segmentIndex = 0; segmentIndex < forkSegments; ++segmentIndex)
			{
				float t0 = float(segmentIndex) / float(forkSegments);
				float t1 = float(segmentIndex + 1) / float(forkSegments);
				vec2 p0 = LightningPoint(forkPoint, forkDirection, aspect, t0, branchSeed + 91.3,
					forkLength, RayBranching);
				vec2 p1 = LightningPoint(forkPoint, forkDirection, aspect, t1, branchSeed + 91.3,
					forkLength, RayBranching);
				if (forkActive > 0.5)
				{
					float along = 0.0;
					float distanceToBolt = LightningSegmentDistance(uv, aspect, p0, p1, along);
					if (distanceToBolt < closestDistance)
					{
						closestDistance = distanceToBolt;
						closestPoint = mix(p0, p1, along);
						closestDirection = forkDirection;
						closestT = forkT + (1.0 - forkT) * mix(t0, t1, along);
					}
				}
			}
		}

		float pixelScale = 1.0 / max(sourceSize.y, 1.0);
		float coreWidth = pixelScale * (1.0 + 2.5 * RayBranching);
		float core = exp(-pow(closestDistance / max(coreWidth, 0.00001), 2.0));
		float glow = exp(-pow(closestDistance / max(coreWidth * 5.0, 0.00001), 2.0));
		vec2 safePoint = clamp(closestPoint, vec2(0.001), vec2(0.999));
		vec2 pathStep = normalize(closestDirection / aspect) * pixelScale * 5.0;
		float depth0 = texture(depthTexture, clamp(safePoint - pathStep, vec2(0.001), vec2(0.999))).r;
		float depth1 = texture(depthTexture, safePoint).r;
		float depth2 = texture(depthTexture, clamp(safePoint + pathStep, vec2(0.001), vec2(0.999))).r;
		float emitterDepth = (depth0 + depth1 + depth2) / 3.0;
		float occlusionDepth = min(depth0, min(depth1, depth2));
		float occlusion = 1.0 - DepthOcclusion *
			smoothstep(0.0, 0.22, currentDepth - occlusionDepth);
		vec2 gradient = vec2(dFdx(depth1), dFdy(depth1));
		float gradientLength = length(gradient);
		float edge = clamp(gradientLength * EdgeGain, 0.0, 1.0);
		float edgeEmission = mix(0.08, 1.0, edge);
		float gate = DepthGate(emitterDepth);
		vec2 screenDirection = normalize(closestDirection / aspect);
		float surfaceAlignment = gradientLength > 0.00001
			? abs(dot(normalize(gradient), screenDirection)) : 1.0;
		float normalFactor = mix(1.0, surfaceAlignment, NormalAlignment);

		float pulseNoise = ElectricValueNoise(safePoint * (3.0 + RayDensity * 0.08) +
			vec2(time * 0.70 + seed, time * 0.41 - seed));
		float phase = time * (2.5 + RayFlicker * 13.0) + seed +
			pulseNoise * 5.0 + closestT * 8.0;
		float pulse = 0.60 + 0.40 * sin(phase);
		float front = fract(time * (0.30 + RayFlicker * 0.95) + seed * 0.037);
		float frontPulse = exp(-pow((closestT - front) / 0.12, 2.0));
		float discharge = mix(0.90, clamp(0.45 + pulse * 0.42 + frontPulse * 0.62, 0.0, 1.0), RayFlicker);
		float endpointFade = 1.0 - 0.22 * closestT;
		float attenuation = max(discharge, 0.0) * occlusion * gate * normalFactor * edgeEmission * endpointFade;
		return vec3(core * 1.35, glow * 0.58, glow * 0.32 + core * 0.90) * attenuation;
	}

	vec3 RayField(vec2 uv, vec2 sourceSize, float currentDepth)
	{
		vec2 origin = vec2(RayOriginX, RayOriginY);
		vec2 aspect = vec2(sourceSize.x / max(sourceSize.y, 1.0), 1.0);
		float density = clamp((RayDensity - 1.0) / 31.0, 0.0, 1.0);
		float activeBolts = mix(1.0, 6.0, density);
		vec3 total = vec3(0.0);
		for (int boltIndex = 0; boltIndex < 6; ++boltIndex)
		{
			float active = step(float(boltIndex), activeBolts - 0.5);
			float normalizedIndex = activeBolts > 1.0
				? float(boltIndex) / max(activeBolts - 1.0, 1.0) : 0.5;
			float angle = RayAngle * 0.01745329252 +
				(normalizedIndex - 0.5) * RaySpread * 6.2831853;
			vec2 direction = vec2(cos(angle), sin(angle));
			float seed = float(boltIndex) * 17.13 + 1.7;
			float lengthScale = 0.78 + 0.44 * CctvHash(vec2(seed, 83.7));
			vec2 rootPerpendicular = vec2(-direction.y, direction.x);
			vec2 rootOffset = direction * ((CctvHash(vec2(seed, 91.4)) - 0.5) * 0.06) +
				rootPerpendicular * ((CctvHash(vec2(seed, 97.2)) - 0.5) *
					(0.08 + RaySpread * 0.10));
			vec2 boltOrigin = clamp(origin + rootOffset / aspect, vec2(0.01), vec2(0.99));
			total += LightningBolt(uv, sourceSize, aspect, currentDepth, boltOrigin, direction,
				seed, max(RayLength, 0.02) * lengthScale) * active;
		}
		return clamp(total / max(activeBolts * 0.72, 1.0), 0.0, 1.0);
	}

	void main()
		{
			vec4 source = texture(inputTexture, i_uv);
			vec4 depth = texture(depthTexture, i_uv);
			float value = clamp(depth.r, 0.0, 1.0);
			float bands = max(2.0, DepthBands);
			if (DepthBands > 0.5 && OutputStyle < 2.5)
			{
				value = clamp(floor(value * bands) / (bands - 1.0), 0.0, 1.0);
			}
			vec3 mappedColor = vec3(value);
			if (OutputStyle > 0.5 && OutputStyle < 1.5)
			{
				mappedColor = ThermalDepth(value);
			}
			else if (OutputStyle > 1.5 && OutputStyle < 2.5)
			{
				mappedColor = vec3(step(SilhouetteThreshold, value));
			}
			else if (OutputStyle > 2.5 && OutputStyle < 3.5)
			{
				mappedColor = vec3(DepthEdge(i_uv));
			}
			else if (OutputStyle > 3.5 && OutputStyle < 4.5)
			{
				vec2 sourceSize = vec2(textureSize(inputTexture, 0));
				float mono = dot(source.rgb, vec3(0.299, 0.587, 0.114));
				float scan = 1.0 - CCTVScanlines * 0.22 *
					(0.5 + 0.5 * sin(i_uv.y * sourceSize.y * 3.14159265));
				float noise = (CctvHash(i_uv * sourceSize + vec2(time * 61.0, time * 37.0)) - 0.5) *
					CCTVNoise * 0.18;
				mappedColor = vec3(mono * 0.16, mono * 0.82, mono * 0.42) * scan;
				mappedColor += vec3(noise) + vec3(value * 0.18);
			}
			else if (OutputStyle > 4.5)
			{
				vec2 texel = 1.0 / vec2(textureSize(depthTexture, 0));
				vec2 sourceSize = vec2(textureSize(inputTexture, 0));
				bool useAura = OutputStyle < 5.5 || OutputStyle > 6.5;
				bool useRays = OutputStyle > 5.5;
				float aura = useAura ? AuraField(i_uv, texel) : 0.0;
				vec3 rayField = vec3(0.0);
				if (useRays)
				{
					rayField = RayField(i_uv, sourceSize, value);
				}
				float rayCore = rayField.x;
				float rayGlow = rayField.y;
				float reactiveLight = rayField.z;
				float colorPhase = clamp(0.5 + 0.5 * sin(time * (1.0 + RayFlicker * 4.0) + value * 6.2831853), 0.0, 1.0);
				vec3 electricColor = mix(ElectricColor, ElectricColor2, colorPhase);
				vec3 coreColor = mix(electricColor, vec3(1.0), 0.72);
				float noise = (CctvHash(i_uv * sourceSize + vec2(time * 61.0, time * 37.0)) - 0.5) * CCTVNoise * 0.18;
				vec3 reactiveSource = source.rgb * (0.18 + aura * 0.10 + reactiveLight * 0.95);
				vec3 electricEmission = electricColor * (aura * 0.72 + rayGlow * 0.92) * ElectricEnergy +
					coreColor * rayCore * 1.55 * ElectricEnergy;
				mappedColor = reactiveSource + electricEmission;
				mappedColor += vec3(noise) + vec3(CCTVScanlines * 0.04 * sin(i_uv.y * sourceSize.y * 3.14159265));
			}
			float outputAlpha = OutputAlpha > 0.5 ? 1.0 : source.a;
			vec4 mapped = vec4(clamp(mappedColor, 0.0, 1.0) * outputAlpha, outputAlpha);
			fragColor = mix(source, mapped, clamp(EffectMix, 0.0, 1.0));
		}
	)";

float Clamp01(float value) {
	return std::max(0.0f, std::min(1.0f, value));
}

bool SamePipelineSettings(const lucida_depth::Settings& left,
	const lucida_depth::Settings& right) noexcept {
	constexpr float kParameterEpsilon = 1.0e-5f;
	const auto close = [kParameterEpsilon](float a, float b) noexcept {
		return std::abs(a - b) <= kParameterEpsilon;
	};
	return left.model == right.model && left.quality == right.quality &&
		close(left.far_percentile, right.far_percentile) &&
		close(left.near_percentile, right.near_percentile) &&
		close(left.contrast, right.contrast) && left.invert == right.invert &&
		close(left.temporal_stability, right.temporal_stability) &&
		left.custom_short_edge == right.custom_short_edge &&
		left.linear_to_srgb == right.linear_to_srgb &&
		left.use_alpha_for_levels == right.use_alpha_for_levels &&
		close(left.alpha_threshold, right.alpha_threshold);
}

} // namespace

LUCIDA_DEPTH::LUCIDA_DEPTH() : Effect(false) {
	SetMinInputs(1);
	SetMaxInputs(1);
	AddParam(ParamOption::Create("Model", {{"ZipDepth", 0.0f}, {"Depth Anything V2 Small", 1.0f}}, 0));
	AddParam(ParamOption::Create("Quality", {{"Fast", 0.0f}, {"Balanced", 1.0f}, {"High", 2.0f}, {"Custom", 3.0f}}, 0));
	AddParam(ParamRange::Create("FarPercentile", 2.0f, ParamRange::Range(0.0f, 25.0f)));
	AddParam(ParamRange::Create("NearPercentile", 98.0f, ParamRange::Range(75.0f, 100.0f)));
	AddParam(ParamRange::Create("Contrast", 1.0f, ParamRange::Range(0.1f, 4.0f)));
	AddParam(ParamBool::Create("Invert", false));
	AddParam(ParamRange::Create("TemporalStability", 0.0f, ParamRange::Range(0.0f, 100.0f)));
	AddParam(ParamRange::CreateInteger("CustomShortEdge", 768, ParamRange::Range(256.0f, 2160.0f)));
	AddParam(ParamOption::Create("InputTransfer", {{"Assume sRGB", 0.0f}, {"Linear to sRGB", 1.0f}}, 0));
	AddParam(ParamBool::Create("UseAlphaForLevels", true));
	AddParam(ParamRange::Create("AlphaThreshold", 0.0f, ParamRange::Range(0.0f, 100.0f)));
	AddParam(ParamOption::Create("OutputAlpha", {{"Preserve Source Alpha", 0.0f}, {"Opaque", 1.0f}}, 0));
	AddParam(ParamRange::Create("EffectMix", 1.0f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamOption::Create("InferenceRate", {{"Every Frame", 0.0f}, {"Every 2 Frames", 1.0f}, {"Every 3 Frames", 2.0f}, {"Every 4 Frames", 3.0f}}, 1));
	AddParam(ffglqs::ParamTrigger::Create("ResetTemporal"));
	AddParam(ParamOption::Create("OutputStyle", {{"Depth Map", 0.0f}, {"Thermal Depth", 1.0f}, {"Silhouette", 2.0f}, {"Depth Edges", 3.0f}, {"CCTV Composite", 4.0f}, {"CCTV Aura", 5.0f}, {"CCTV Rays", 6.0f}, {"CCTV Aura + Rays", 7.0f}}, 0));
	AddParam(ParamRange::CreateInteger("DepthBands", 0, ParamRange::Range(0.0f, 32.0f)));
	AddParam(ParamRange::Create("SilhouetteThreshold", 0.5f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("EdgeGain", 12.0f, ParamRange::Range(1.0f, 32.0f)));
	AddParam(ParamRange::Create("CCTVScanlines", 0.0f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("CCTVNoise", 0.0f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::CreateInteger("AuraRadius", 6, ParamRange::Range(1.0f, 32.0f)));
	AddParam(ParamRange::Create("AuraFalloff", 1.5f, ParamRange::Range(0.1f, 4.0f)));
	AddParam(ParamRange::Create("RayLength", 0.45f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("RaySpread", 0.35f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::CreateInteger("RayDensity", 10, ParamRange::Range(1.0f, 32.0f)));
	AddParam(ParamRange::Create("RayBranching", 0.55f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("RayFlicker", 0.45f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("DepthOcclusion", 0.8f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("ElectricEnergy", 2.0f, ParamRange::Range(0.0f, 4.0f)));
	AddParam(ParamRange::Create("RayOriginX", 0.5f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("RayOriginY", 0.5f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("EmissionDepth", 0.5f, ParamRange::Range(0.0f, 1.0f)));
	AddParam(ParamRange::Create("DepthGateWidth", 1.0f, ParamRange::Range(0.01f, 1.0f)));
	AddParam(ParamRange::Create("NormalAlignment", 0.0f, ParamRange::Range(0.0f, 1.0f)));
	AddRGBColorParam("ElectricColor");
	AddRGBColorParam("ElectricColor2");
	AddParam(ParamRange::Create("RayAngle", 0.0f, ParamRange::Range(0.0f, 360.0f)));
	GetParam("ElectricColor")->SetValue(0.05f);
	GetParam("ElectricColor_green")->SetValue(0.75f);
	GetParam("ElectricColor_blue")->SetValue(1.0f);
	GetParam("ElectricColor2")->SetValue(0.75f);
	GetParam("ElectricColor2_green")->SetValue(0.95f);
	GetParam("ElectricColor2_blue")->SetValue(1.0f);
	SetParamDisplayName(PARAM_MODEL, "Model", false);
	SetParamDisplayName(PARAM_QUALITY, "Quality", false);
	SetParamDisplayName(PARAM_FAR, "Far Percentile", false);
	SetParamDisplayName(PARAM_NEAR, "Near Percentile", false);
	SetParamDisplayName(PARAM_CONTRAST, "Contrast", false);
	SetParamDisplayName(PARAM_INVERT, "Invert", false);
	SetParamDisplayName(PARAM_TEMPORAL, "Temporal Stability", false);
	SetParamDisplayName(PARAM_CUSTOM_EDGE, "Custom Short Edge", false);
	SetParamDisplayName(PARAM_TRANSFER, "Input Transfer", false);
	SetParamDisplayName(PARAM_USE_ALPHA, "Use Alpha for Levels", false);
	SetParamDisplayName(PARAM_ALPHA_THRESHOLD, "Alpha Threshold", false);
	SetParamDisplayName(PARAM_OUTPUT_ALPHA, "Output Alpha", false);
	SetParamDisplayName(PARAM_EFFECT_MIX, "Effect Mix", false);
	SetParamDisplayName(PARAM_INFERENCE_RATE, "Inference Rate", false);
	SetParamDisplayName(PARAM_RESET_TEMPORAL, "Reset Temporal", false);
	SetParamDisplayName(PARAM_OUTPUT_STYLE, "Output Style", false);
	SetParamDisplayName(PARAM_DEPTH_BANDS, "Depth Bands", false);
	SetParamDisplayName(PARAM_SILHOUETTE_THRESHOLD, "Silhouette Threshold", false);
	SetParamDisplayName(PARAM_EDGE_GAIN, "Edge Gain", false);
	SetParamDisplayName(PARAM_CCTV_SCANLINES, "CCTV Scanlines", false);
	SetParamDisplayName(PARAM_CCTV_NOISE, "CCTV Noise", false);
	SetParamDisplayName(PARAM_AURA_RADIUS, "Aura Radius", false);
	SetParamDisplayName(PARAM_AURA_FALLOFF, "Aura Falloff", false);
	SetParamDisplayName(PARAM_RAY_LENGTH, "Ray Length", false);
	SetParamDisplayName(PARAM_RAY_SPREAD, "Ray Spread", false);
	SetParamDisplayName(PARAM_RAY_DENSITY, "Ray Density", false);
	SetParamDisplayName(PARAM_RAY_BRANCHING, "Ray Branching", false);
	SetParamDisplayName(PARAM_RAY_FLICKER, "Ray Flicker", false);
	SetParamDisplayName(PARAM_DEPTH_OCCLUSION, "Depth Occlusion", false);
	SetParamDisplayName(PARAM_ELECTRIC_ENERGY, "Electric Energy", false);
	SetParamDisplayName(PARAM_RAY_ORIGIN_X, "Ray Origin X", false);
	SetParamDisplayName(PARAM_RAY_ORIGIN_Y, "Ray Origin Y", false);
	SetParamDisplayName(PARAM_EMISSION_DEPTH, "Emission Depth", false);
	SetParamDisplayName(PARAM_DEPTH_GATE_WIDTH, "Depth Gate Width", false);
	SetParamDisplayName(PARAM_NORMAL_ALIGNMENT, "Normal Alignment", false);
	SetParamDisplayName(PARAM_RAY_ANGLE, "Ray Angle", false);
	SetParamGroup(PARAM_MODEL, "DepthGen");
	SetParamGroup(PARAM_QUALITY, "DepthGen");
	SetParamGroup(PARAM_FAR, "DepthGen");
	SetParamGroup(PARAM_NEAR, "DepthGen");
	SetParamGroup(PARAM_CONTRAST, "DepthGen");
	SetParamGroup(PARAM_INVERT, "DepthGen");
	SetParamGroup(PARAM_CUSTOM_EDGE, "Input");
	SetParamGroup(PARAM_TRANSFER, "Input");
	SetParamGroup(PARAM_USE_ALPHA, "Input");
	SetParamGroup(PARAM_ALPHA_THRESHOLD, "Input");
	SetParamGroup(PARAM_TEMPORAL, "Temporal / Performance");
	SetParamGroup(PARAM_INFERENCE_RATE, "Temporal / Performance");
	SetParamGroup(PARAM_RESET_TEMPORAL, "Temporal / Performance");
	SetParamGroup(PARAM_OUTPUT_STYLE, "CCTV VFX");
	SetParamGroup(PARAM_DEPTH_BANDS, "CCTV VFX");
	SetParamGroup(PARAM_SILHOUETTE_THRESHOLD, "CCTV VFX");
	SetParamGroup(PARAM_EDGE_GAIN, "CCTV VFX");
	SetParamGroup(PARAM_CCTV_SCANLINES, "CCTV VFX");
	SetParamGroup(PARAM_CCTV_NOISE, "CCTV VFX");
	SetParamGroup(PARAM_AURA_RADIUS, "Electric Field");
	SetParamGroup(PARAM_AURA_FALLOFF, "Electric Field");
	SetParamGroup(PARAM_RAY_LENGTH, "Electric Field");
	SetParamGroup(PARAM_RAY_SPREAD, "Electric Field");
	SetParamGroup(PARAM_RAY_DENSITY, "Electric Field");
	SetParamGroup(PARAM_RAY_BRANCHING, "Electric Field");
	SetParamGroup(PARAM_RAY_FLICKER, "Electric Field");
	SetParamGroup(PARAM_DEPTH_OCCLUSION, "Electric Field");
	SetParamGroup(PARAM_ELECTRIC_ENERGY, "Electric Field");
	SetParamGroup(PARAM_RAY_ORIGIN_X, "Electric Field");
	SetParamGroup(PARAM_RAY_ORIGIN_Y, "Electric Field");
	SetParamGroup(PARAM_EMISSION_DEPTH, "Electric Field");
	SetParamGroup(PARAM_DEPTH_GATE_WIDTH, "Electric Field");
	SetParamGroup(PARAM_NORMAL_ALIGNMENT, "Electric Field");
	SetParamGroup(PARAM_RAY_ANGLE, "Electric Field");
	SetParamGroup(PARAM_ELECTRIC_COLOR, "Electric Field");
	SetParamGroup(PARAM_ELECTRIC_COLOR_GREEN, "Electric Field");
	SetParamGroup(PARAM_ELECTRIC_COLOR_BLUE, "Electric Field");
	SetParamGroup(PARAM_ELECTRIC_COLOR_2, "Electric Field");
	SetParamGroup(PARAM_ELECTRIC_COLOR_2_GREEN, "Electric Field");
	SetParamGroup(PARAM_ELECTRIC_COLOR_2_BLUE, "Electric Field");
	SetParamGroup(PARAM_OUTPUT_ALPHA, "Output");
	SetParamGroup(PARAM_EFFECT_MIX, "Output");
	SetFragmentShader(kFragmentShader);
	Log("LUCIDA Depth constructor loaded");
}

LUCIDA_DEPTH::~LUCIDA_DEPTH() {
	Clean();
}

FFResult LUCIDA_DEPTH::InitGL(const FFGLViewportStruct* viewport) {
	Log("LUCIDA Depth InitGL begin");
	const std::string fragment_shader_code = CreateFragmentShader(fragmentShaderBase);
	if (!shader.Compile(vertexShaderCode, fragment_shader_code)) {
		Log("LUCIDA Depth InitGL shader compilation failed");
		DeInitGL();
		return FF_FAIL;
	}
	Log("LUCIDA Depth InitGL shader compiled");
	if (!quad.Initialise()) {
		Log("LUCIDA Depth InitGL screen quad initialization failed");
		DeInitGL();
		return FF_FAIL;
	}
	Log("LUCIDA Depth InitGL screen quad initialized");
	if (Init() == FF_FAIL) {
		Log("LUCIDA Depth InitGL DepthGen initialization failed");
		DeInitGL();
		return FF_FAIL;
	}
	const FFResult result = CFFGLPlugin::InitGL(viewport);
	Log(std::string("LUCIDA Depth InitGL result=") + std::to_string(result));
	return result;
}

FFResult LUCIDA_DEPTH::ProcessOpenGL(ProcessOpenGLStruct* input_textures) {
	if (!process_logged_) {
		Log("LUCIDA Depth ProcessOpenGL called");
		process_logged_ = true;
	}
	return Effect::ProcessOpenGL(input_textures);
}

void LUCIDA_DEPTH::Log(const std::string& message) const {
	FFGLLog::LogToHost(message.c_str());
#ifdef _WIN32
	char temp[MAX_PATH] = {};
	const DWORD length = GetTempPathA(static_cast<DWORD>(sizeof(temp)), temp);
	if (length > 0 && length < sizeof(temp)) {
		const std::string path = std::string(temp) + "LUCIDA_Depth_runtime.log";
		static std::once_flag reset_log_once;
		std::call_once(reset_log_once, [&path] {
			std::ofstream reset(path, std::ios::trunc);
			if (reset) reset << "--- LUCIDA Depth session ---\n";
		});
		std::ofstream file(path, std::ios::app);
		if (file) file << message << '\n';
	}
#endif
}

FFResult LUCIDA_DEPTH::Init() {
	inference_worker_.Start();
	return FF_SUCCESS;
}

void LUCIDA_DEPTH::Update() {
	if (GetFloatParameter(PARAM_RESET_TEMPORAL) > 0.5f) {
		reset_temporal_requested_ = true;
	}
	const bool custom_edge_visible = lucida_depth_ffgl::OptionIndex(GetFloatParameter(PARAM_QUALITY), 4) == 3;
	const bool alpha_threshold_visible = GetFloatParameter(PARAM_USE_ALPHA) > 0.5f;
	const int cctv_style = lucida_depth_ffgl::OptionIndex(GetFloatParameter(PARAM_OUTPUT_STYLE), 8);
	if (!visibility_initialized_ || custom_edge_visible != custom_edge_visible_ ||
		alpha_threshold_visible != alpha_threshold_visible_ || cctv_style != cctv_style_) {
		const bool raise_event = visibility_initialized_;
		SetParamVisibility(PARAM_CUSTOM_EDGE, custom_edge_visible, raise_event);
		SetParamVisibility(PARAM_ALPHA_THRESHOLD, alpha_threshold_visible, raise_event);
		SetParamVisibility(PARAM_DEPTH_BANDS, cctv_style <= 1, raise_event);
		SetParamVisibility(PARAM_SILHOUETTE_THRESHOLD, cctv_style == 2, raise_event);
		SetParamVisibility(PARAM_EDGE_GAIN, cctv_style == 3 || cctv_style >= 5, raise_event);
		const bool electric_visible = cctv_style >= 5;
		const bool aura_visible = cctv_style == 5 || cctv_style == 7;
		const bool rays_visible = cctv_style == 6 || cctv_style == 7;
		SetParamVisibility(PARAM_CCTV_SCANLINES, cctv_style >= 4, raise_event);
		SetParamVisibility(PARAM_CCTV_NOISE, cctv_style >= 4, raise_event);
		SetParamVisibility(PARAM_AURA_RADIUS, aura_visible, raise_event);
		SetParamVisibility(PARAM_AURA_FALLOFF, aura_visible, raise_event);
		SetParamVisibility(PARAM_RAY_LENGTH, rays_visible, raise_event);
		SetParamVisibility(PARAM_RAY_SPREAD, rays_visible, raise_event);
		SetParamVisibility(PARAM_RAY_DENSITY, rays_visible, raise_event);
		SetParamVisibility(PARAM_RAY_BRANCHING, rays_visible, raise_event);
		SetParamVisibility(PARAM_RAY_ANGLE, rays_visible, raise_event);
		SetParamVisibility(PARAM_RAY_FLICKER, electric_visible, raise_event);
		SetParamVisibility(PARAM_DEPTH_OCCLUSION, electric_visible, raise_event);
		SetParamVisibility(PARAM_ELECTRIC_ENERGY, electric_visible, raise_event);
		SetParamVisibility(PARAM_RAY_ORIGIN_X, rays_visible, raise_event);
		SetParamVisibility(PARAM_RAY_ORIGIN_Y, rays_visible, raise_event);
		SetParamVisibility(PARAM_EMISSION_DEPTH, electric_visible, raise_event);
		SetParamVisibility(PARAM_DEPTH_GATE_WIDTH, electric_visible, raise_event);
		SetParamVisibility(PARAM_NORMAL_ALIGNMENT, rays_visible, raise_event);
		SetParamVisibility(PARAM_ELECTRIC_COLOR, electric_visible, raise_event);
		SetParamVisibility(PARAM_ELECTRIC_COLOR_GREEN, electric_visible, raise_event);
		SetParamVisibility(PARAM_ELECTRIC_COLOR_BLUE, electric_visible, raise_event);
		SetParamVisibility(PARAM_ELECTRIC_COLOR_2, electric_visible, raise_event);
		SetParamVisibility(PARAM_ELECTRIC_COLOR_2_GREEN, electric_visible, raise_event);
		SetParamVisibility(PARAM_ELECTRIC_COLOR_2_BLUE, electric_visible, raise_event);
		custom_edge_visible_ = custom_edge_visible;
		alpha_threshold_visible_ = alpha_threshold_visible;
		cctv_style_ = cctv_style;
		visibility_initialized_ = true;
	}
}

void LUCIDA_DEPTH::ReleaseDepthTexture() {
	if (depth_texture_ != 0) {
		glDeleteTextures(1, &depth_texture_);
	}
	depth_texture_ = 0;
	depth_width_ = 0;
	depth_height_ = 0;
}

void LUCIDA_DEPTH::ReleaseReadbackPbos() {
	for (int index = 0; index < kReadbackPboCount; ++index) {
		if (readback_pbo_fences_[index] != nullptr) {
			glDeleteSync(readback_pbo_fences_[index]);
			readback_pbo_fences_[index] = nullptr;
		}
		readback_pbo_in_flight_[index] = false;
	}
	if (readback_pbos_[0] != 0) {
		glDeleteBuffers(kReadbackPboCount, readback_pbos_);
	}
	for (GLuint& pbo : readback_pbos_) pbo = 0;
	readback_pbo_bytes_ = 0;
	readback_pbo_width_ = 0;
	readback_pbo_height_ = 0;
	readback_pbo_write_index_ = 0;
}

bool LUCIDA_DEPTH::EnsureReadbackPbos(int width, int height) {
	if (width <= 0 || height <= 0) return false;
	const size_t bytes = static_cast<size_t>(width) * static_cast<size_t>(height) * 4U;
	if (readback_pbos_[0] != 0 &&
		readback_pbo_bytes_ == bytes && readback_pbo_width_ == width && readback_pbo_height_ == height) {
		return true;
	}
	ReleaseReadbackPbos();
	glGenBuffers(kReadbackPboCount, readback_pbos_);
	if (readback_pbos_[0] == 0) {
		ReleaseReadbackPbos();
		return false;
	}
	GLint previous_pbo = 0;
	glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING, &previous_pbo);
	for (GLuint pbo : readback_pbos_) {
		glBindBuffer(GL_PIXEL_PACK_BUFFER, pbo);
		glBufferData(GL_PIXEL_PACK_BUFFER, static_cast<GLsizeiptr>(bytes), nullptr, GL_STREAM_READ);
	}
	glBindBuffer(GL_PIXEL_PACK_BUFFER, static_cast<GLuint>(previous_pbo));
	if (glGetError() != GL_NO_ERROR) {
		ReleaseReadbackPbos();
		return false;
	}
	readback_pbo_bytes_ = bytes;
	readback_pbo_width_ = width;
	readback_pbo_height_ = height;
	return true;
}

bool LUCIDA_DEPTH::EnsureDepthTexture(int width, int height) {
	if (width <= 0 || height <= 0) return false;
	if (depth_texture_ != 0 && depth_width_ == width && depth_height_ == height) return true;
	ReleaseDepthTexture();
	ReleaseReadbackPbos();
	glGenTextures(1, &depth_texture_);
	if (depth_texture_ == 0) return false;
	std::vector<float> neutral(static_cast<size_t>(width) * static_cast<size_t>(height), 0.0f);
	glBindTexture(GL_TEXTURE_2D, depth_texture_);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
	glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, width, height, 0, GL_RED, GL_FLOAT, neutral.data());
	glBindTexture(GL_TEXTURE_2D, 0);
	if (glGetError() != GL_NO_ERROR) {
		ReleaseDepthTexture();
		return false;
	}
	depth_width_ = width;
	depth_height_ = height;
	return true;
}

bool LUCIDA_DEPTH::ReadInputTexture(const FFGLTextureStruct& input, std::string* error) {
	if (input.Handle == 0 || input.Width == 0 || input.Height == 0) {
		if (error) *error = "FFGL input texture is null or has zero dimensions.";
		return false;
	}
	const int content_width = static_cast<int>(input.Width);
	const int content_height = static_cast<int>(input.Height);
	const int hardware_width = std::max(content_width, static_cast<int>(input.HardwareWidth));
	const int hardware_height = std::max(content_height, static_cast<int>(input.HardwareHeight));
	if (!EnsureReadbackPbos(hardware_width, hardware_height)) {
		if (error) *error = "Could not allocate asynchronous FFGL readback buffers.";
		return false;
	}
	texture_readback_rgba_.resize(static_cast<size_t>(hardware_width) * static_cast<size_t>(hardware_height) * 4U);
	GLint previous_active = GL_TEXTURE0;
	GLint previous_texture = 0;
	GLint previous_pbo = 0;
	GLint previous_pack = 4;
	glGetIntegerv(GL_ACTIVE_TEXTURE, &previous_active);
	glActiveTexture(GL_TEXTURE0);
	glGetIntegerv(GL_TEXTURE_BINDING_2D, &previous_texture);
	glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING, &previous_pbo);
	glGetIntegerv(GL_PACK_ALIGNMENT, &previous_pack);
	glPixelStorei(GL_PACK_ALIGNMENT, 1);
	glBindTexture(GL_TEXTURE_2D, input.Handle);
	bool completed_readback = false;
	int completed_index = -1;
	for (int index = 0; index < kReadbackPboCount; ++index) {
		if (!readback_pbo_in_flight_[index]) continue;
		const GLenum wait_result = glClientWaitSync(readback_pbo_fences_[index], 0, 0);
		if (wait_result == GL_ALREADY_SIGNALED || wait_result == GL_CONDITION_SATISFIED) {
			completed_index = index;
			break;
		}
		if (wait_result == GL_WAIT_FAILED) {
			glDeleteSync(readback_pbo_fences_[index]);
			readback_pbo_fences_[index] = nullptr;
			readback_pbo_in_flight_[index] = false;
		}
	}
	if (completed_index >= 0) {
		glBindBuffer(GL_PIXEL_PACK_BUFFER, readback_pbos_[completed_index]);
		void* mapped = glMapBufferRange(GL_PIXEL_PACK_BUFFER, 0,
			static_cast<GLsizeiptr>(readback_pbo_bytes_), GL_MAP_READ_BIT);
		if (mapped == nullptr) {
			glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(previous_texture));
			glBindBuffer(GL_PIXEL_PACK_BUFFER, static_cast<GLuint>(previous_pbo));
			glPixelStorei(GL_PACK_ALIGNMENT, previous_pack);
			glActiveTexture(static_cast<GLenum>(previous_active));
			if (error) *error = "Could not map a completed asynchronous FFGL readback buffer.";
			return false;
		}
		std::memcpy(texture_readback_rgba_.data(), mapped, readback_pbo_bytes_);
		const GLboolean unmapped = glUnmapBuffer(GL_PIXEL_PACK_BUFFER);
		if (unmapped == GL_FALSE) {
			glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(previous_texture));
			glBindBuffer(GL_PIXEL_PACK_BUFFER, static_cast<GLuint>(previous_pbo));
			glPixelStorei(GL_PACK_ALIGNMENT, previous_pack);
			glActiveTexture(static_cast<GLenum>(previous_active));
			if (error) *error = "A completed asynchronous FFGL readback buffer became invalid.";
			return false;
		}
		glDeleteSync(readback_pbo_fences_[completed_index]);
		readback_pbo_fences_[completed_index] = nullptr;
		readback_pbo_in_flight_[completed_index] = false;
		completed_readback = true;
	}
	int write_index = -1;
	for (int offset = 0; offset < kReadbackPboCount; ++offset) {
		const int index = (readback_pbo_write_index_ + offset) % kReadbackPboCount;
		if (!readback_pbo_in_flight_[index]) {
			write_index = index;
			break;
		}
	}
	GLenum read_error = GL_NO_ERROR;
	if (write_index >= 0) {
		glBindBuffer(GL_PIXEL_PACK_BUFFER, readback_pbos_[write_index]);
		glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
		read_error = glGetError();
		if (read_error == GL_NO_ERROR) {
			readback_pbo_fences_[write_index] = glFenceSync(GL_SYNC_GPU_COMMANDS_COMPLETE, 0);
			if (readback_pbo_fences_[write_index] != nullptr) {
				readback_pbo_in_flight_[write_index] = true;
				readback_pbo_write_index_ = (write_index + 1) % kReadbackPboCount;
			} else {
				// Very old/non-conformant contexts may expose PBOs but not GL sync.
				// Finish only in this compatibility path; normal Resolume contexts
				// stay fully non-blocking here.
				glFinish();
				void* mapped = glMapBufferRange(GL_PIXEL_PACK_BUFFER, 0,
					static_cast<GLsizeiptr>(readback_pbo_bytes_), GL_MAP_READ_BIT);
				if (mapped != nullptr) {
					std::memcpy(texture_readback_rgba_.data(), mapped, readback_pbo_bytes_);
					completed_readback = glUnmapBuffer(GL_PIXEL_PACK_BUFFER) != GL_FALSE;
				}
			}
		}
	}
	glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(previous_texture));
	glBindBuffer(GL_PIXEL_PACK_BUFFER, static_cast<GLuint>(previous_pbo));
	glPixelStorei(GL_PACK_ALIGNMENT, previous_pack);
	glActiveTexture(static_cast<GLenum>(previous_active));
	if (read_error != GL_NO_ERROR) {
		if (error) *error = "glGetTexImage failed with OpenGL error " + std::to_string(read_error) + ".";
		return false;
	}
	if (!completed_readback) return false;
	readback_rgba_.resize(static_cast<size_t>(content_width) * static_cast<size_t>(content_height) * 4U);
	for (int y = 0; y < content_height; ++y) {
		const unsigned char* source = texture_readback_rgba_.data() +
			static_cast<size_t>(y) * static_cast<size_t>(hardware_width) * 4U;
		unsigned char* destination = readback_rgba_.data() +
			static_cast<size_t>(y) * static_cast<size_t>(content_width) * 4U;
		std::copy(source, source + static_cast<size_t>(content_width) * 4U, destination);
	}
	return true;
}

void LUCIDA_DEPTH::UploadDepthTexture() {
	if (depth_texture_ == 0 || depth_values_.empty()) return;
	GLint previous_active = GL_TEXTURE0;
	GLint previous_texture = 0;
	GLint previous_unpack = 4;
	glGetIntegerv(GL_ACTIVE_TEXTURE, &previous_active);
	glActiveTexture(GL_TEXTURE0);
	glGetIntegerv(GL_TEXTURE_BINDING_2D, &previous_texture);
	glGetIntegerv(GL_UNPACK_ALIGNMENT, &previous_unpack);
	glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
	glBindTexture(GL_TEXTURE_2D, depth_texture_);
	glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, depth_width_, depth_height_, GL_RED, GL_FLOAT, depth_values_.data());
	glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(previous_texture));
	glPixelStorei(GL_UNPACK_ALIGNMENT, previous_unpack);
	glActiveTexture(static_cast<GLenum>(previous_active));
}

lucida_depth::Settings LUCIDA_DEPTH::ReadSettings() {
	lucida_depth::Settings settings;
	settings.model = lucida_depth_ffgl::ModelFromOption(GetFloatParameter(PARAM_MODEL));
	settings.quality = lucida_depth_ffgl::QualityFromOption(GetFloatParameter(PARAM_QUALITY));
	settings.far_percentile = GetFloatParameter(PARAM_FAR);
	settings.near_percentile = GetFloatParameter(PARAM_NEAR);
	settings.contrast = GetFloatParameter(PARAM_CONTRAST);
	settings.invert = GetFloatParameter(PARAM_INVERT) > 0.5f;
	settings.temporal_stability = GetFloatParameter(PARAM_TEMPORAL);
	settings.custom_short_edge = static_cast<int>(std::lround(GetFloatParameter(PARAM_CUSTOM_EDGE)));
	settings.linear_to_srgb = lucida_depth_ffgl::LinearTransferFromOption(GetFloatParameter(PARAM_TRANSFER));
	settings.use_alpha_for_levels = GetFloatParameter(PARAM_USE_ALPHA) > 0.5f;
	settings.alpha_threshold = GetFloatParameter(PARAM_ALPHA_THRESHOLD) / 100.0f;
	settings.preserve_alpha = lucida_depth_ffgl::PreserveAlphaFromOption(GetFloatParameter(PARAM_OUTPUT_ALPHA));
	return settings;
}

void LUCIDA_DEPTH::DrawOutput(const FFGLTextureStruct& input) {
	ffglex::ScopedShaderBinding shader_binding(shader.GetGLID());
	ffglex::ScopedSamplerActivation input_sampler(0);
	ffglex::Scoped2DTextureBinding input_binding(input.Handle);
	shader.Set("inputTexture", 0);
	ffglex::ScopedSamplerActivation depth_sampler(1);
	ffglex::Scoped2DTextureBinding depth_binding(depth_texture_);
	shader.Set("depthTexture", 1);
	shader.Set("EffectMix", Clamp01(GetFloatParameter(PARAM_EFFECT_MIX)));
	const FFGLTexCoords max_coords = GetMaxGLTexCoords(input);
	shader.Set("maxUV", max_coords.s, max_coords.t);
	quad.Draw();
}

void LUCIDA_DEPTH::Clean() {
	ReleaseDepthTexture();
	ReleaseReadbackPbos();
	inference_worker_.Stop();
	readback_rgba_.clear();
	texture_readback_rgba_.clear();
	depth_values_.clear();
	source_alpha_.clear();
	has_depth_ = false;
	have_settings_ = false;
	last_settings_ = {};
	settings_generation_ = 1;
	render_counter_ = 0;
	process_logged_ = false;
	inference_logs_ = 0;
	visibility_initialized_ = false;
	reset_temporal_requested_ = false;
	cctv_style_ = -1;
}

FFResult LUCIDA_DEPTH::Render(ProcessOpenGLStruct* input_textures) {
	if (!input_textures || input_textures->numInputTextures < 1 ||
		!input_textures->inputTextures || !input_textures->inputTextures[0]) return FF_FAIL;
	const FFGLTextureStruct& input = *input_textures->inputTextures[0];
	if (!render_logged_) {
		Log("LUCIDA Depth Render recibido: " + std::to_string(input.Width) + "x" +
			std::to_string(input.Height) + " hardware=" + std::to_string(input.HardwareWidth) +
			"x" + std::to_string(input.HardwareHeight));
		render_logged_ = true;
	}
	if (!EnsureDepthTexture(static_cast<int>(input.Width), static_cast<int>(input.Height))) return FF_FAIL;
	try {
		const lucida_depth::Settings settings = ReadSettings();
		if (reset_temporal_requested_) {
			reset_temporal_requested_ = false;
			inference_worker_.ResetTemporal();
			++settings_generation_;
			has_depth_ = false;
			Log("LUCIDA Depth temporal history reset");
		}
		if (!have_settings_ || !SamePipelineSettings(settings, last_settings_)) {
			last_settings_ = settings;
			have_settings_ = true;
			++settings_generation_;
			has_depth_ = false;
		}
		LUCIDA_InferenceResult completed;
		if (inference_worker_.TryTake(&completed)) {
			if (completed.settings_generation == settings_generation_ && completed.success) {
				depth_values_ = std::move(completed.depth);
				source_alpha_ = std::move(completed.alpha);
				has_depth_ = true;
				UploadDepthTexture();
				if (inference_logs_ < 8) {
					Log(std::string("LUCIDA Depth inference model=") +
						depthgen::DepthModelName(completed.model) +
						" provider=" +
						depthgen::InferenceProviderName(completed.provider) +
						" worker_ms=" + std::to_string(completed.elapsed_ms) +
						" short_edge=" + std::to_string(completed.inference_short_edge));
					++inference_logs_;
				}
			} else if (completed.settings_generation == settings_generation_ && !completed.error.empty()) {
				Log("LUCIDA Depth: " + completed.error);
			}
		}
		const int inference_rate = lucida_depth_ffgl::InferenceRateFromOption(GetFloatParameter(PARAM_INFERENCE_RATE));
		const bool should_infer = !has_depth_ ||
			(render_counter_ % static_cast<std::uint64_t>(inference_rate) == 0);
		std::string error;
		if (should_infer && ReadInputTexture(input, &error)) {
			const std::int32_t current_time = static_cast<std::int32_t>(
				std::llround(std::isfinite(hostTime) && hostTime != 0.0 ? hostTime * 1000.0 : frame_time_));
			const std::int32_t step = have_time_ ? std::max<std::int32_t>(1, current_time - previous_time_) : 1;
			LUCIDA_InferenceJob job;
			job.rgba = std::move(readback_rgba_);
			job.width = static_cast<int>(input.Width);
			job.height = static_cast<int>(input.Height);
			job.settings_generation = settings_generation_;
			job.settings = settings;
			job.time = current_time;
			job.time_step = step;
			inference_worker_.Submit(std::move(job));
			previous_time_ = current_time;
			have_time_ = true;
			++frame_time_;
		} else if (!error.empty()) {
			Log("LUCIDA Depth lectura de textura falló: " + error);
		}
		++render_counter_;
		DrawOutput(input);
		return FF_SUCCESS;
	} catch (const std::exception& exception) {
		Log(std::string("LUCIDA Depth contained exception: ") + exception.what());
		try { DrawOutput(input); } catch (...) {}
		return FF_SUCCESS;
	} catch (...) {
		Log("LUCIDA Depth contained an unknown exception.");
		try { DrawOutput(input); } catch (...) {}
		return FF_SUCCESS;
	}
}
