export interface RiskScore {
    id: number;
    asset_id: number;
    calculated_date: string;
    overall_score: number;
    condition_score: number;
    usage_score: number;
    climate_score: number;
    redundancy_score: number;
    population_impact_score: number;
    explanation: string;
}

export interface Asset {
    id: number;
    name: string;
    type: string;
    latitude: number;
    longitude: number;
    province: string;
    municipality?: string;
    year_built?: number;
    last_inspection_date?: string;
    condition_index?: number;
    daily_usage?: number;
    criticality?: string;
    redundancy_available: boolean;
    climate_zone?: string;
    serves_essential_services: boolean;
    risk_scores: RiskScore[];
}

// Government Dashboard Types
export interface ConditionBreakdown {
    condition: string;
    count: number;
    percentage: number;
}

export interface DashboardSummary {
    region: string;
    total_bridges: number;
    condition_breakdown: ConditionBreakdown[];
    replacement_value_billions: number;
    priority_investment_millions: number;
    currency: string;
    last_updated: string;
    data_source: string;
    data_source_url?: string;
    reference_year?: string;
    is_live_data?: boolean;
    is_cached?: boolean;
    cache_age_hours?: number | null;
}

export interface CacheStatus {
    region: string;
    cached: boolean;
    valid: boolean;
    cached_at?: string;
    age_hours?: number;
    ttl_hours?: number;
    expires_in_hours?: number;
    sync_status?: string;
    total_bridges?: number;
    message?: string;
}

export interface BridgeLocation {
    id: string;
    name: string;
    latitude: number;
    longitude: number;
    condition: string;
    condition_index?: string;
    year_built: number | string;
    last_inspection: string;
    region: string;
    highway?: string;
    structure_type?: string;
    category?: string;
    material?: string;
    owner?: string;
    status?: string;
    county?: string;
    source?: string;
}

export interface BridgeLocationsResponse {
    region: string;
    bridges: BridgeLocation[];
    count: number;
    data_source: string;
}

export interface RegionsResponse {
    regions: string[];
    default_region: string;
    count: number;
}

// Condition color mapping
export const CONDITION_COLORS: Record<string, string> = {
    "Good": "#22c55e",      // green-500
    "Fair": "#eab308",      // yellow-500
    "Poor": "#f97316",      // orange-500
    "Critical": "#ef4444",  // red-500
    "Unknown": "#94a3b8",   // slate-400
};

export const CONDITION_BG_COLORS: Record<string, string> = {
    "Good": "bg-green-500",
    "Fair": "bg-yellow-500",
    "Poor": "bg-orange-500",
    "Critical": "bg-red-500",
    "Unknown": "bg-slate-400",
};

export const CONDITION_TEXT_COLORS: Record<string, string> = {
    "Good": "text-green-600",
    "Fair": "text-yellow-600",
    "Poor": "text-orange-600",
    "Critical": "text-red-600",
    "Unknown": "text-slate-500",
};

// Road Degradation Types (Feature 10)
export interface RoadSegment {
    highway: string;
    direction: string;
    section_from: string;
    section_to: string;
    km_start: number;
    km_end: number;
    pci: number;
    condition: string;
    dmi: number;
    iri: number;
    pavement_type: string;
    functional_class: string;
    province: string;
    lat: number;
    lng: number;
    aadt: number;
    pavement_age: number;
}

export interface RoadForecast {
    highway: string;
    section: string;
    current_pci: number;
    predicted_pci: Record<number, number>;
    years_to_critical: number;
    optimal_intervention_year: number;
    optimal_intervention_pci: number;
    estimated_cost_now: number;
    estimated_cost_optimal: number;
    estimated_cost_delayed: number;
    cost_savings_optimal: number;
    degradation_rate: number;
}

export interface ForecastSummary {
    average_pci: number;
    critical_sections: number;
    poor_sections: number;
    total_cost_if_repaired_now: number;
    total_cost_at_optimal_time: number;
    potential_savings: number;
}

export interface EconomicImpact {
    highway: string;
    section: string;
    pci: number;
    condition: string;
    daily_traffic: number;
    annual_vehicle_damage_cost: number;
    annual_fuel_waste_cost: number;
    annual_freight_delay_cost: number;
    total_annual_cost: number;
    roi_if_repaired: number;
}

export interface HeatmapSegment {
    highway: string;
    section: string;
    lat: number;
    lng: number;
    pci: number;
    condition: string;
    aadt: number;
    color: string;
    weight: number;
    province: string;
    pavement_type: string;
}

// ============================================
// Feature 11: Winter Resilience Types
// ============================================

export interface WinterVulnerability {
    highway: string;
    direction: string;
    section_from: string;
    section_to: string;
    km_start: number;
    km_end: number;
    current_pci: number;
    current_condition: string;
    pavement_type: string;
    climate_zone: string;
    freeze_thaw_cycles: number;
    pci_vulnerability_factor: number;
    pavement_vulnerability_factor: number;
    traffic_load_factor: number;
    drainage_factor: number;
    winter_damage_risk_score: number;
    risk_level: 'severe' | 'high' | 'moderate' | 'low';
    expected_pci_loss: number;
    post_winter_pci: number;
    post_winter_condition: string;
    crosses_threshold: boolean;
    threshold_crossed: string;
    recommendation: string;
    recommended_action: string;
    pre_winter_cost: number;
    spring_repair_cost: number;
    cost_savings: number;
    roi: number;
}

export interface WinterForecastSummary {
    province: string;
    highway: string;
    winter_season: string;
    total_sections: number;
    risk_distribution: {
        severe: number;
        high: number;
        moderate: number;
        low: number;
    };
    total_km_at_risk: number;
    average_expected_pci_loss: number;
    sections_crossing_threshold: number;
    financials: {
        total_pre_winter_investment: number;
        total_spring_repair_avoided: number;
        total_potential_savings: number;
        overall_roi: number;
    };
}

export interface PreWinterIntervention {
    highway: string;
    section: string;
    current_pci: number;
    option_a: {
        name: string;
        action: string;
        cost: number;
        pci_loss: number;
        spring_pci: number;
    };
    option_b: {
        name: string;
        pci_loss: number;
        spring_pci: number;
        emergency_repair_cost: number;
        traffic_disruption_weeks: number;
    };
    analysis: {
        cost_savings: number;
        roi_multiplier: number;
        recommendation: string;
    };
}

// ============================================
// Feature 12: Corridor Optimization Types
// ============================================

export interface BundleSection {
    section_from: string;
    section_to: string;
    km_start: number;
    km_end: number;
    pci: number;
    condition: string;
}

export interface BundleOpportunity {
    bundle_id: string;
    highway: string;
    direction: string;
    geometry: {
        start_km: number;
        end_km: number;
        total_length_km: number;
        continuous_smooth_km: number;
    };
    condition: {
        average_pci: number;
        min_pci: number;
        max_pci: number;
        sections_count: number;
    };
    cost_analysis: {
        individual_approach_cost: number;
        bundled_approach_cost: number;
        savings: number;
        savings_percent: number;
        mobilization_savings: number;
    };
    benefits: {
        traffic_disruptions_avoided: number;
        qualifies_for_federal_funding: boolean;
        federal_funding_threshold: number;
    };
    sections: BundleSection[];
}

export interface DirectionalAnalysis {
    highway: string;
    km_range: string;
    direction_1: {
        name: string;
        sections: number;
        avg_pci: number;
        avg_iri: number;
        avg_dmi: number;
        truck_percent: number;
    };
    direction_2: {
        name: string;
        sections: number;
        avg_pci: number;
        avg_iri: number;
        avg_dmi: number;
        truck_percent: number;
    };
    comparison: {
        pci_difference: number;
        worse_direction: string;
        degradation_reason: string;
    };
    recommendation: {
        action: string;
        single_direction_cost: number;
        both_directions_cost: number;
        potential_savings: number;
    };
}

export interface CorridorSummary {
    province: string;
    highway: string;
    bundles: {
        total_bundles: number;
        total_sections_bundled: number;
        total_bundled_length_km: number;
    };
    savings: {
        total_individual_cost: number;
        total_bundled_cost: number;
        total_savings: number;
        average_savings_percent: number;
    };
    directional: {
        directions_with_disparity: number;
        single_direction_opportunities: number;
    };
    top_opportunity: {
        bundle_id: string;
        savings: number;
    };
}


