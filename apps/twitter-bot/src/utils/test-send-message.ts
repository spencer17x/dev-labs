import dayjs from 'dayjs';
import { Telegraf } from 'telegraf';
import { config } from '../config';

// 请将下面的 BOT_TOKEN 和 CHAT_ID 替换为你自己的
const BOT_TOKEN = config.telegram.botToken;
const CHAT_ID = '-1002229721331'; // 例如 -1001234567890

const bot = new Telegraf(BOT_TOKEN);

async function sendTestMessage() {
  try {
    const text = [
      `1*xxx* 发推了`,
      `内容: xxxx`,
      `当前时间: ${dayjs(Date.now()).format('YYYY-MM-DD HH:mm:ss')}`,
      `链接: https://x.com/teslaownersSV/status/1946388626537054717`,
    ].join('\n');

    await bot.telegram.sendMessage(CHAT_ID, text, {
      parse_mode: 'Markdown',
    });
    console.log('消息发送成功');
  } catch (error) {
    console.error('消息发送失败:', error);
  } finally {
    process.exit();
  }
}

sendTestMessage();
