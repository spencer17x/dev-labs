import assert from 'node:assert/strict';
import test from 'node:test';

import { mergeSignalContextWithDexTokenDetail } from './dex-token-context.ts';

test('dex token detail merge backfills token identity and social metadata', () => {
  const merged = mergeSignalContextWithDexTokenDetail(
    {
      token: {
        address: '9gLshEn5yRPf7vQPjXF558RiVu5hR2Eg8yPNa67ipump',
        chain: 'solana',
      },
      dexscreener: {
        links: [{ type: 'twitter', url: 'https://x.com/anoncoinit' }],
        socials: [{ platform: 'twitter', url: 'https://x.com/anoncoinit' }],
        websites: ['https://anime.example'],
      },
    },
    {
      fdv: 24_500,
      marketCap: 24_000,
      token: {
        name: 'Anime Dogecoin',
        symbol: 'aDOGE',
      },
      socials: [
        { platform: 'twitter', url: 'https://x.com/anoncoinit' },
        { platform: 'telegram', url: 'https://t.me/anime_doge' },
      ],
      websites: ['https://anime.example', 'https://adoge.fun'],
    },
  );

  assert.equal(merged.token?.name, 'Anime Dogecoin');
  assert.equal(merged.token?.symbol, 'aDOGE');
  assert.equal(merged.dexscreener?.fdv, 24_500);
  assert.deepEqual(merged.dexscreener?.websites, [
    'https://anime.example',
    'https://adoge.fun',
  ]);
  assert.deepEqual(merged.dexscreener?.socials, [
    { handle: null, platform: 'twitter', url: 'https://x.com/anoncoinit' },
    { handle: null, platform: 'telegram', url: 'https://t.me/anime_doge' },
  ]);
});
