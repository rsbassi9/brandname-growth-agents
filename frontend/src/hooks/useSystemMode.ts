import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function useSystemMode() {
  return useQuery({
    queryKey: ["system", "mode"],
    queryFn: api.mode,
  });
}
