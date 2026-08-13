const DIGITS = /\D/g

function onlyDigits(value) {
  return String(value || '').replace(DIGITS, '')
}

export function validateStir(value, { required = false } = {}) {
  const raw = String(value || '').trim()
  if (!raw) return required ? 'STIR kiritilishi shart.' : null
  const digits = onlyDigits(raw)
  if (digits.length !== 9) return 'STIR 9 ta raqamdan iborat bo‘lishi kerak.'
  return null
}

export function validateJshshir(value, { required = false } = {}) {
  const raw = String(value || '').trim()
  if (!raw) return required ? 'JSHSHIR kiritilishi shart.' : null
  const digits = onlyDigits(raw)
  if (digits.length !== 14) return 'JSHSHIR 14 ta raqamdan iborat bo‘lishi kerak.'
  if (!'123456'.includes(digits[0])) return 'JSHSHIR birinchi raqami noto‘g‘ri.'
  const weights = [7, 3, 1]
  const total = digits.slice(0, 13).split('').reduce((sum, ch, i) => sum + Number(ch) * weights[i % 3], 0)
  if (total % 10 !== Number(digits[13])) return 'JSHSHIR kontrol raqami noto‘g‘ri.'
  return null
}

export function validateMfo(value, { required = false } = {}) {
  const raw = String(value || '').trim()
  if (!raw) return required ? 'MFO kiritilishi shart.' : null
  const digits = onlyDigits(raw)
  if (digits.length !== 5) return 'MFO 5 ta raqamdan iborat bo‘lishi kerak.'
  return null
}

export function validateBankAccount(value, { required = false } = {}) {
  const raw = String(value || '').trim()
  if (!raw) return required ? 'Hisob raqami kiritilishi shart.' : null
  const digits = onlyDigits(raw)
  if (digits.length !== 20) return 'Hisob raqami 20 ta raqamdan iborat bo‘lishi kerak.'
  return null
}

export function validateOked(value, { required = false } = {}) {
  const raw = String(value || '').trim()
  if (!raw) return required ? 'OKED kiritilishi shart.' : null
  const digits = onlyDigits(raw)
  if (digits.length !== 5) return 'OKED 5 ta raqamdan iborat bo‘lishi kerak.'
  return null
}

export function validateUzPhone(value, { required = false } = {}) {
  const raw = String(value || '').trim()
  if (!raw) return required ? 'Telefon kiritilishi shart.' : null
  const digits = onlyDigits(raw)
  let local = ''
  if (digits.startsWith('998') && digits.length === 12) local = digits.slice(3)
  else if (digits.length === 9 && digits[0] === '9') local = digits
  else return 'Telefon formati: +998 XX XXX XX XX.'
  if (local[0] !== '9') return 'Telefon mobil raqam +998 9X ... bilan boshlanishi kerak.'
  return null
}

export function normalizeUzPhone(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  const digits = onlyDigits(raw)
  let local = ''
  if (digits.startsWith('998') && digits.length === 12) local = digits.slice(3)
  else if (digits.length === 9 && digits[0] === '9') local = digits
  else return raw
  return `+998${local}`
}

export function validateCompanyProfile(form) {
  const errors = {}
  const checks = [
    ['stir', validateStir, {}],
    ['director_jshshr', validateJshshir, {}],
    ['mfo', validateMfo, {}],
    ['bank_account', validateBankAccount, {}],
    ['oked', validateOked, {}],
    ['phone', validateUzPhone, {}],
  ]
  checks.forEach(([key, fn, opts]) => {
    const message = fn(form[key], opts)
    if (message) errors[key] = message
  })
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = 'E-mail noto‘g‘ri.'
  }
  return errors
}

export function validateClientFields(form) {
  const errors = {}
  if (form.client_type === 'legal') {
    if (!(form.company_name || '').trim()) errors.company_name = 'Korxona nomi kiritilishi shart'
    const phoneErr = validateUzPhone(form.phone, { required: true })
    if (phoneErr) errors.phone = phoneErr
    const innErr = validateStir(form.inn, { required: false })
    if (innErr) errors.inn = innErr
    const mfoErr = validateMfo(form.mfo, { required: false })
    if (mfoErr) errors.mfo = mfoErr
  } else {
    if (!(form.full_name || '').trim()) errors.full_name = 'To‘liq ism kiritilishi shart'
    const pinflErr = validateJshshir(form.pinfl, { required: true })
    if (pinflErr) errors.pinfl = pinflErr
    if (!(form.passport_number || '').trim()) errors.passport_number = 'Pasport kiritilishi shart'
    const phoneErr = validateUzPhone(form.phone, { required: true })
    if (phoneErr) errors.phone = phoneErr
  }
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = 'E-mail noto‘g‘ri'
  }
  return errors
}
