// Read only the public message fields. Validation input/context may contain SSH secrets.
const message = value => typeof value === 'string' ? value.trim() : '';
const detailMessage = (detail, labels) => {
  if (typeof detail === 'string') return message(detail);
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return '';
  const text = message(detail.msg) || message(detail.message);
  if (!text) return '';
  const field = Array.isArray(detail.loc) ? detail.loc.find(part => typeof part === 'string' && Object.hasOwn(labels, part)) : null;
  return field ? `${labels[field]}: ${text}` : text;
};

export function nodeRequestError(error, labels = {}, fallback = 'Operation failed') {
  const data = error?.response?.data;
  const details = Array.isArray(data?.detail) ? data.detail : [data?.detail];
  return details.map(detail => detailMessage(detail, labels)).filter(Boolean).join(' · ')
    || message(data?.msg) || message(error?.message) || fallback;
}
