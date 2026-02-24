export const CITIES = [
  "Seoul", "Busan", "Daegu", "Daejeon", "Gwangju",
  "Incheon", "Gangneung", "Jeju", "Cheongju", "Ulsan",
] as const;

export type CityName = (typeof CITIES)[number];

export const CITY_COLORS: Record<string, string> = {
  Seoul: "#3B82F6",
  Busan: "#10B981",
  Daegu: "#F59E0B",
  Daejeon: "#EF4444",
  Gwangju: "#8B5CF6",
  Incheon: "#06B6D4",
  Gangneung: "#F97316",
  Jeju: "#EC4899",
  Cheongju: "#14B8A6",
  Ulsan: "#6366F1",
};
