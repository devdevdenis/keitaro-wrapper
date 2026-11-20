import { http } from './http'

export const api = {
  health: () => http.get('/health'),

  // справочники
  countries: () => http.get('/countries'),
  domains: () => http.get('/keitaro/domains'),
  groups: () => http.get('/keitaro/groups'),
  trafficSources: () => http.get('/keitaro/traffic-sources'),
  offers: () => http.get('/keitaro/offers'),

  // кампании
  listCampaigns: ({ mine = true } = {}) => http.get(`/campaigns?mine=${mine}`),
  getCampaign: (id) => http.get(`/campaigns/${id}`),
  createCampaign: (data) => http.post('/campaigns', data),

  // редактор офферов в потоке
  addStreamOffer: (streamId, offerId) =>
    http.post(`/streams/${streamId}/offers`, { offer_id: offerId }),
  removeStreamOffer: (streamId, offerId) => http.delete(`/streams/${streamId}/offers/${offerId}`),
}

export { ApiError } from './http'
