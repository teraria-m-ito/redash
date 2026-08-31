import { axios } from "@/services/axios";

export default {
  generateQuery: data => axios.post("api/ai/generate_query", data),
  listSqlPairs: dataSourceId => axios.get("api/ai/sql_pairs", { params: { data_source_id: dataSourceId } }),
  createSqlPair: data => axios.post("api/ai/sql_pairs", data),
  deleteSqlPair: id => axios.delete(`api/ai/sql_pairs/${id}`),
};
