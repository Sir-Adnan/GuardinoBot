import type { DataProvider } from "@refinedev/core";
import { api } from "./axios";

const API_URL = import.meta.env.VITE_API_URL || "/api";

// Minimal REST data provider for the FastAPI backend. List endpoints return
// `{ items, total }`; a `search` CrudFilter maps to the `search` query param.
// Mutations are stubbed for Phase 1 (read-only resources) and filled in per
// resource as the panel grows.
export const dataProvider: DataProvider = {
  getApiUrl: () => API_URL,

  getList: async ({ resource, pagination, filters }) => {
    const current = pagination?.current ?? 1;
    const pageSize = pagination?.pageSize ?? 20;
    const params: Record<string, unknown> = { page: current, per_page: pageSize };
    const search = (filters ?? []).find(
      (f: any) => f.field === "search" || f.field === "q",
    ) as any;
    if (search && search.value) params.search = search.value;

    const res = await api.get(`/${resource}`, { params });
    const body = res.data;
    return {
      data: body.items ?? body,
      total: body.total ?? (Array.isArray(body) ? body.length : 0),
    };
  },

  getOne: async ({ resource, id }) => {
    const res = await api.get(`/${resource}/${id}`);
    return { data: res.data };
  },

  getMany: async ({ resource, ids }) => {
    const rows = await Promise.all(
      ids.map((id) => api.get(`/${resource}/${id}`).then((r) => r.data)),
    );
    return { data: rows };
  },

  // Required by useCustom (dashboard / reports / automation). Without it those
  // pages crash → blank screen after login.
  custom: async ({ url, method, payload, query, headers }: any) => {
    const res = await api.request({
      url,
      method: (method ?? "get").toLowerCase(),
      params: query,
      data: payload,
      headers,
    });
    return { data: res.data };
  },

  create: async () => {
    throw new Error("create is not implemented yet");
  },
  update: async () => {
    throw new Error("update is not implemented yet");
  },
  deleteOne: async () => {
    throw new Error("delete is not implemented yet");
  },
};
