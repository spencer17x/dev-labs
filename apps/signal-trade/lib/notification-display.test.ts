import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildNotificationIdentity,
  buildNotificationSocialLinks,
} from './notification-display.ts';

test('notification identity prefers token metadata over address fallbacks', () => {
  const identity = buildNotificationIdentity({
    context: {
      token: {
        address: '9gLshEn5yRPf7vQPjXF558RiVu5hR2Eg8yPNa67ipump',
        name: 'Anime Dogecoin',
        symbol: 'aDOGE',
      },
    },
    event: {
      token: {
        address: '9gLshEn5yRPf7vQPjXF558RiVu5hR2Eg8yPNa67ipump',
      },
    },
  });

  assert.equal(identity.primaryLabel, 'aDOGE');
  assert.equal(identity.secondaryLabel, 'Anime Dogecoin');
  assert.equal(identity.address, '9gLshEn5yRPf7vQPjXF558RiVu5hR2Eg8yPNa67ipump');
});

test('notification social links are grouped and deduplicated', () => {
  const links = buildNotificationSocialLinks({
    context: {
      dexscreener: {
        links: [
          { type: 'twitter', url: 'https://x.com/anoncoinit' },
          { type: 'website', url: 'https://adoge.fun' },
        ],
        socials: [
          { platform: 'x', url: 'https://x.com/anoncoinit' },
          { platform: 'telegram', url: 'https://t.me/anime_doge' },
        ],
        websites: ['https://adoge.fun'],
      },
    },
    event: {
      token: {},
    },
  });

  assert.deepEqual(
    links.map(link => ({ type: link.type, url: link.url })),
    [
      { type: 'website', url: 'https://adoge.fun' },
      { type: 'twitter', url: 'https://x.com/anoncoinit' },
      { type: 'telegram', url: 'https://t.me/anime_doge' },
    ],
  );
});
