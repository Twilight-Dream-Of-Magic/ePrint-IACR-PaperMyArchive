#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace iwt {

/// External algorithm plugin contract for strict iwt_core integration.
/// Implementations must express round execution in terms of iwt::atomic_operations
/// so TM-1/TM-2/TM-3 semantics stay aligned with the mainline.
struct PluginAnalyzeConfig {
    std::string crypto_type;   // block | stream | hash
    std::int32_t input_bits{0};
    std::int32_t output_bits{0};
    std::string threat_model;
    std::int32_t seed{0};
};

struct PluginDescriptor {
    std::string name;
    std::string execution_backend{"iwt_core"};
    std::vector<std::string> supported_crypto_types;
};

class IwtCoreAlgorithmPlugin {
public:
    virtual ~IwtCoreAlgorithmPlugin() = default;

    /// Returns static capabilities/metadata.
    virtual PluginDescriptor descriptor() const = 0;

    /// Run analysis and return report JSON payload as UTF-8 string.
    /// The payload must include iwt_core-generated atomic trace evidence.
    virtual std::string analyze_json(const PluginAnalyzeConfig& config) = 0;
};

} // namespace iwt

