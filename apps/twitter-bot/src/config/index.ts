import 'dotenv/config';
import * as process from 'node:process';

export const config = {
  twitter: {
    ct0: process.env.ct0!,
    auth_token: process.env.auth_token!,
    interval: Number(process.env.interval!),
  },
  telegram: {
    botToken: process.env.tg_bot_token!,
    // 注意：不再需要 tg_chat_ids 配置
    // 机器人会动态维护所在的群组列表
  },
};
