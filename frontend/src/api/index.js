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
  listCampaigns: () => http.get('/campaigns'),
  getCampaign: (id) => http.get(`/campaigns/${id}`),
  createCampaign: (data) => http.post('/campaigns', data), // без потоков: в редакторе — шаблоны
  updateCampaign: (id, data) => http.put(`/campaigns/${id}`, data), // сразу в Keitaro
  deleteCampaign: (id) => http.delete(`/campaigns/${id}`), // в Keitaro — в архив

  // потоки: правки копятся в черновике, в Keitaro — по pushStream.
  // streamId — id потока в нашей БД (у нового потока в Keitaro id ещё нет)
  updateStream: (streamId, patch) => http.patch(`/streams/${streamId}`, patch),
  deleteStream: (streamId) => http.delete(`/streams/${streamId}`),
  addStreamOffer: (streamId, offerId) =>
    http.post(`/streams/${streamId}/offers`, { offer_id: offerId }),
  removeStreamOffer: (streamId, offerId) => http.delete(`/streams/${streamId}/offers/${offerId}`),
  restoreStreamOffer: (streamId, offerId) =>
    http.post(`/streams/${streamId}/offers/${offerId}/restore`),
  // × у удалённого оффера — убрать строку из списка насовсем
  forgetStreamOffer: (streamId, offerId) =>
    http.delete(`/streams/${streamId}/offers/${offerId}/row`),
  pinStreamOffer: (streamId, offerId, pinned) =>
    http.put(`/streams/${streamId}/offers/${offerId}/pin`, { pinned }),
  // Push to KT — черновики всех потоков кампании одной пачкой
  pushCampaign: (campaignId) => http.post(`/campaigns/${campaignId}/push`),
  cancelStreamDraft: (streamId) => http.delete(`/streams/${streamId}/draft`),
}

export { ApiError } from './http'
