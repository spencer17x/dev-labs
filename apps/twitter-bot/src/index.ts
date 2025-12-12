import { config } from './config';
import { Bot } from './utils/bot';

const main = async () => {
  const bot = new Bot();
  await bot.start({
    botToken: config.telegram.botToken,
    twitterConfig: {
      ct0: config.twitter.ct0,
      authToken: config.twitter.auth_token,
      interval: config.twitter.interval,
    },
  });
  console.log('Bot launched');
};

main().catch(console.error);
