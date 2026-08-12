import { api } from '../api'

const list = (data) => (Array.isArray(data) ? data : data?.results || [])

export function clientOptionLabel(client) {
  if (!client) return '—'
  const name = client.company_name || client.full_name || '—'
  const id = client.inn || client.pinfl || client.passport_number || client.director_jshshr
  return id ? `${name} · ${id}` : name
}

export function clientSearchText(client) {
  if (!client) return ''
  return [
    client.company_name,
    client.full_name,
    client.first_name,
    client.last_name,
    client.middle_name,
    client.inn,
    client.pinfl,
    client.passport_number,
    client.director_jshshr,
    client.director_fish,
    client.phone,
    client.email,
  ].filter(Boolean).join(' ')
}

export function searchClients(query) {
  return api.clients({ search: query, page_size: 20 }).then(list)
}

export function fetchClient(id) {
  return api.retrieve('/clients/', id)
}
