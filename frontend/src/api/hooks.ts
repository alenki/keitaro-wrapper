import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type {
  Campaign,
  CampaignForm,
  CampaignListItem,
  NewCampaign,
  OfferOption,
  Stream,
} from './types'

export const queryKeys = {
  campaigns: ['campaigns'] as const,
  campaign: (id: number) => ['campaign', id] as const,
  campaignForm: ['campaign-form'] as const,
  offers: (query: string) => ['offers', query] as const,
}

export function useCampaigns() {
  return useQuery({
    queryKey: queryKeys.campaigns,
    queryFn: () => api<CampaignListItem[]>('/api/campaigns'),
  })
}

export function useCampaignForm() {
  return useQuery({
    queryKey: queryKeys.campaignForm,
    queryFn: () => api<CampaignForm>('/api/campaign-form'),
    staleTime: 5 * 60_000,
  })
}

export function useOfferSearch(query: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.offers(query),
    queryFn: () => api<OfferOption[]>(`/api/offers?q=${encodeURIComponent(query)}&limit=20`),
    enabled,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  })
}

export function useCampaign(id: number) {
  return useQuery({
    queryKey: queryKeys.campaign(id),
    queryFn: () => api<Campaign>(`/api/campaigns/${id}`),
  })
}

export function useCreateCampaign() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: NewCampaign) =>
      api<Campaign>('/api/campaigns', { method: 'POST', json: data }),
    onSuccess: (campaign) => {
      queryClient.setQueryData(queryKeys.campaign(campaign.id), campaign)
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaigns })
    },
  })
}

export function useFetchCampaign(id: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api<Campaign>(`/api/campaigns/${id}/fetch`, { method: 'POST' }),
    onSuccess: (campaign) => queryClient.setQueryData(queryKeys.campaign(id), campaign),
  })
}

export type StreamAction =
  | { type: 'add'; offerId: number }
  | { type: 'remove'; offerId: number }
  | { type: 'restore'; offerId: number }
  | { type: 'pin'; offerId: number; pinned: boolean }
  | { type: 'push' }
  | { type: 'cancel' }

function sendAction(streamId: number, action: StreamAction): Promise<Stream> {
  const base = `/api/streams/${streamId}`
  switch (action.type) {
    case 'add':
      return api(`${base}/offers`, { method: 'POST', json: { offer_id: action.offerId } })
    case 'remove':
      return api(`${base}/offers/${action.offerId}`, { method: 'DELETE' })
    case 'restore':
      return api(`${base}/offers/${action.offerId}/restore`, { method: 'POST' })
    case 'pin':
      return api(`${base}/offers/${action.offerId}`, {
        method: 'PATCH',
        json: { pinned: action.pinned },
      })
    case 'push':
      return api(`${base}/push`, { method: 'POST' })
    case 'cancel':
      return api(`${base}/cancel`, { method: 'POST' })
  }
}

/** Every editor action answers with the whole stream, which replaces it in the campaign. */
export function useStreamAction(campaignId: number, streamId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (action: StreamAction) => sendAction(streamId, action),
    onSuccess: (stream) => {
      queryClient.setQueryData<Campaign>(queryKeys.campaign(campaignId), (campaign) =>
        campaign
          ? { ...campaign, streams: campaign.streams.map((s) => (s.id === stream.id ? stream : s)) }
          : campaign,
      )
    },
  })
}
