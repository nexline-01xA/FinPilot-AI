'use client';

import { useState } from 'react';
import { api } from '@/lib/api';

export default function DemoResetButton() {
  const [status, setStatus] = useState('');

  return (
    <button
      onClick={async () => {
        setStatus('Resetting…');
        try {
          await api.reset();
          setStatus('Reset complete. Refresh pages.');
        } catch (error) {
          setStatus(String(error));
        }
      }}
      className="rounded-lg border border-paper-200 px-3 py-2 text-sm"
    >
      Reset NovaCart demo
      {status && <span className="ml-2 text-xs text-ink-600">{status}</span>}
    </button>
  );
}
