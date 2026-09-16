#pragma once

#include <FFGLSDK.h>

class LucidaGuide final : public ffglqs::Effect
{
public:
	LucidaGuide();
	~LucidaGuide() override = default;

	const char* GetShortName() override
	{
		static const char* shortName = "LucidaGuide";
		return shortName;
	}
};
