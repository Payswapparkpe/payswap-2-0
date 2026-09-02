import { OrderEvent, OrderMode, OrderStatus, PartnerOrder } from '../models/onboarding.models';

export function invoiceIdFor(orderId: string): string {
  return `INV-${orderId.replace(/^ord_/, '').toUpperCase()}`;
}

export function hydrateOrder(raw: PartnerOrder): PartnerOrder {
  const createdAt = raw.createdAt;
  const mode: OrderMode = raw.mode ?? (raw.note?.toLowerCase().includes('test') ? 'test' : 'live');
  const timeline =
    raw.timeline?.length
      ? raw.timeline
      : timelineForStatus(raw.status, createdAt);
  return {
    ...raw,
    mode,
    updatedAt: raw.updatedAt || timeline[timeline.length - 1]?.at || createdAt,
    timeline,
    invoiceId: raw.invoiceId || invoiceIdFor(raw.id),
    fulfilmentCodes: raw.fulfilmentCodes ?? (raw.status === 'fulfilled' ? sampleCodes(raw, 8) : []),
    legalName: raw.legalName || '',
    poNumber: raw.poNumber || '',
  };
}

export function timelineForStatus(status: OrderStatus, createdAt: string): OrderEvent[] {
  const events: OrderEvent[] = [{ status: 'placed', at: createdAt, note: 'Order received' }];
  if (status === 'placed') {
    return events;
  }
  if (status === 'cancelled') {
    events.push({ status: 'cancelled', at: createdAt, note: 'Order cancelled' });
    return events;
  }
  events.push({ status: 'processing', at: createdAt, note: 'Fulfilment started' });
  if (status === 'processing') {
    return events;
  }
  if (status === 'fulfilled') {
    events.push({ status: 'fulfilled', at: createdAt, note: 'Codes / cards delivered' });
  }
  return events;
}

export function appendEvent(order: PartnerOrder, status: OrderStatus, note: string): OrderEvent[] {
  return [...(order.timeline ?? []), { status, at: new Date().toISOString(), note }];
}

export function sampleCodes(order: PartnerOrder, max = 12): string[] {
  const prefix = order.kind === 'prepaid_card' ? 'CARD' : 'VCH';
  const n = Math.min(order.quantity, max);
  return Array.from({ length: n }, (_, i) => {
    const seq = String(i + 1).padStart(4, '0');
    return `${prefix}-${order.brand.slice(0, 3).toUpperCase()}-${order.id.slice(-4).toUpperCase()}-${seq}`;
  });
}

export function kindLabel(kind: string): string {
  if (kind === 'corporate_gifting') return 'Gifting (legacy)';
  if (kind === 'brand_voucher') return 'Brand voucher';
  return 'Prepaid card';
}

export function trackerSteps(status: OrderStatus): { id: OrderStatus; label: string; state: 'done' | 'active' | 'todo' | 'skip' }[] {
  if (status === 'cancelled') {
    return [
      { id: 'placed', label: 'Placed', state: 'done' },
      { id: 'cancelled', label: 'Cancelled', state: 'active' },
    ];
  }
  const order: OrderStatus[] = ['placed', 'processing', 'fulfilled'];
  const idx = Math.max(order.indexOf(status), 0);
  return order.map((id, i) => ({
    id,
    label: id === 'placed' ? 'Placed' : id === 'processing' ? 'Processing' : 'Fulfilled',
    state: i < idx ? 'done' : i === idx ? 'active' : 'todo',
  }));
}

export function invoiceHtml(order: PartnerOrder, partnerName: string): string {
  const when = new Date(order.createdAt).toLocaleString('en-IN');
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${order.invoiceId}</title>
  <style>body{font-family:system-ui,sans-serif;padding:32px;color:#13101c}table{width:100%;border-collapse:collapse;margin-top:24px}th,td{text-align:left;padding:8px;border-bottom:1px solid #eee}h1{margin:0}</style>
  </head><body>
  <h1>Payswap tax invoice</h1>
  <p>${order.invoiceId} · ${order.mode === 'test' ? 'TEST (not a tax invoice)' : 'Tax invoice'}</p>
  <p>Bill to: <strong>${partnerName || order.legalName || 'Partner'}</strong></p>
  <p>Date: ${when}</p>
  <table>
    <tr><th>Description</th><th>Qty</th><th>Unit</th><th>Amount</th></tr>
    <tr><td>${order.title} · ${order.brand}</td><td>${order.quantity}</td>
    <td>₹${order.unitValue.toLocaleString('en-IN')}</td><td>₹${order.amount.toLocaleString('en-IN')}</td></tr>
  </table>
  <p>GST as applicable on the commercial schedule. Demo document for the partner console.</p>
  </body></html>`;
}

export function downloadText(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function generateFilePassword(): string {
  return `PSW-${crypto.randomUUID().replace(/-/g, '').slice(0, 8).toUpperCase()}`;
}

export function lockedFileText(order: PartnerOrder): string {
  return [
    'PAYSWAP LOCKED FULFILMENT FILE',
    `Order: ${order.id}`,
    `PO: ${order.poNumber || '—'}`,
    `Original file: ${order.fulfilmentFile?.fileName || 'attachment'}`,
    '',
    'This demo wrapper is not the real codes file.',
    'Open the order in the partner console, request OTP 123456, then download the real attachment.',
  ].join('\n');
}

function downloadDataUrl(fileName: string, dataUrl: string): void {
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = fileName;
  a.click();
}

export function publicOrder(order: PartnerOrder, isAdmin: boolean): PartnerOrder {
  const row = hydrateOrder(order);
  if (isAdmin) {
    return structuredClone(row);
  }
  return structuredClone({
    ...row,
    filePassword: '',
    fulfilmentFile: row.fulfilmentFile
      ? { fileName: row.fulfilmentFile.fileName, mimeType: row.fulfilmentFile.mimeType, dataUrl: '' }
      : undefined,
  });
}
