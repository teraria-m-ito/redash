import { axios } from "@/services/axios";

const saveOrCreateUrl = data => (data.id ? `api/insights/${data.id}` : "api/insights");

const transformRequest = data => {
  const newData = Object.assign({}, data);
  if (newData.query_id === undefined && newData.query) {
    newData.query_id = newData.query.id;
    delete newData.query;
  }
  delete newData.results;
  delete newData.user;
  return newData;
};

const Insight = {
  query: () => axios.get("api/insights"),
  get: ({ id }) => axios.get(`api/insights/${id}`),
  save: data => axios.post(saveOrCreateUrl(data), transformRequest(data)),
  delete: data => axios.delete(`api/insights/${data.id}`),
  evaluate: data => axios.post(`api/insights/${data.id}/eval`),
};

export default Insight;
