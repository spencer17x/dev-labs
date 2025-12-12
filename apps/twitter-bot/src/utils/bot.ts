import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import { Context, NarrowedContext, Telegraf } from 'telegraf';

import { Update } from 'telegraf/typings/core/types/typegram';
import { DBUtil } from './db';
import { Config, TwitterUtil } from './twitter';

export interface LaunchOptions {
  botToken: string;
  twitterConfig: Config;
}

dayjs.extend(utc);
dayjs.extend(timezone);

export class Bot {
  private bot!: Telegraf;
  private twitterUtil!: TwitterUtil;
  dbUtil!: DBUtil;

  /**
   * 启动机器人
   * @param options
   */
  async start(options: LaunchOptions) {
    const { botToken, twitterConfig } = options;

    this.dbUtil = new DBUtil();

    this.bot = new Telegraf(botToken);
    this.bot.on('my_chat_member', this.handleMyChatMember.bind(this));
    this.bot.command('help', this.handleHelp.bind(this));
    this.bot.command('sub', this.handleSub.bind(this));
    this.bot.command('unsub', this.handleUnSub.bind(this));
    this.bot.command('users', this.handleUsers.bind(this));
    this.bot.command('groups', this.handleGroups.bind(this));
    this.bot.command('admin', this.handleAdmin.bind(this));
    this.bot.command('admins', this.handleAdmins.bind(this));
    this.bot.command('debug', this.handleDebug.bind(this));

    await new Promise(resolve => {
      this.bot.launch(() => {
        resolve(null);
      });
    });
    this.bot.start(ctx => {
      ctx.reply(
        `🤖 欢迎使用 Twitter 转发机器人！

这个机器人可以监控指定的 Twitter 用户并将推文转发到群组。

💡 输入 /help 查看所有可用命令
🚀 输入 /groups 查看当前群组状态

开始使用吧！`,
        { parse_mode: 'Markdown' },
      );
    });

    console.log('Telegram bot launched');

    // 显示当前群组信息
    const groups = this.dbUtil.getGroups() || [];
    const users = this.dbUtil.getUsers() || [];
    console.log(`📊 机器人状态:`);
    console.log(`   📱 当前所在群组: ${groups.length} 个`);
    groups.forEach((group, index) => {
      console.log(`      ${index + 1}. "${group.title}" (${group.type}, ID: ${group.id})`);
    });
    console.log(`   👥 已订阅用户: ${users.length} 个 [${users.join(', ')}]`);

    this.twitterUtil = await TwitterUtil.create(twitterConfig);
    this.checkUpdate();
  }

  /**
   * 处理机器人被添加/移除到群组或频道
   * @param ctx
   */
  handleMyChatMember(ctx: NarrowedContext<Context<Update>, Update.MyChatMemberUpdate>) {
    const { chat, new_chat_member, old_chat_member, from } = ctx.update.my_chat_member;

    // 详细的调试日志
    console.log(`🔍 接收到 my_chat_member 事件:`);
    console.log(
      `   群组信息: ${'title' in chat ? chat.title : 'No Title'} (${chat.type}, ID: ${chat.id})`,
    );
    console.log(`   旧状态: ${old_chat_member.status}`);
    console.log(`   新状态: ${new_chat_member.status}`);
    console.log(
      `   操作者: ${from.first_name}${from.username ? ` (@${from.username})` : ''} (ID: ${from.id})`,
    );

    // 定义状态类型
    const inactiveStates = ['left', 'kicked'];
    const activeStates = ['administrator', 'member'];

    // 机器人被添加到群组/频道 (从非活跃状态 -> 活跃状态)
    if (
      inactiveStates.includes(old_chat_member.status) &&
      activeStates.includes(new_chat_member.status)
    ) {
      if (chat.type === 'group' || chat.type === 'channel' || chat.type === 'supergroup') {
        const chatTitle = 'title' in chat ? chat.title : 'Unknown';
        console.log(`✅ 机器人被添加到 ${chat.type} "${chatTitle}" (ID: ${chat.id})`);
        console.log(`   状态变更: ${old_chat_member.status} → ${new_chat_member.status}`);
        console.log(
          `   添加者: ${from.first_name}${from.username ? ` (@${from.username})` : ''} (ID: ${from.id})`,
        );

        try {
          this.dbUtil.addGroup(chat.id, {
            title: chatTitle || 'Unknown',
            type: chat.type,
            fromId: from.id,
            fromUsername: from.username || '',
          });

          // 验证保存结果
          const groups = this.dbUtil.getGroups();
          const isAdded = groups?.some(group => group.id === chat.id);

          if (isAdded) {
            console.log(`   ✅ 群组已成功保存到数据库`);
          } else {
            console.error(`   ❌ 群组保存失败 - 未在数据库中找到`);
          }

          // 获取当前所有群组数量
          const totalGroups = groups?.length || 0;
          console.log(`   📊 当前机器人总共在 ${totalGroups} 个群组中`);
        } catch (error) {
          console.error(`   ❌ 保存群组信息时出错:`, error);
        }
      } else {
        console.log(`⚠️  忽略非群组聊天: ${chat.type}`);
      }
    }

    // 机器人被移除出群组/频道 (从活跃状态 -> 非活跃状态)
    else if (
      activeStates.includes(old_chat_member.status) &&
      inactiveStates.includes(new_chat_member.status)
    ) {
      if (chat.type === 'group' || chat.type === 'channel' || chat.type === 'supergroup') {
        const chatTitle = 'title' in chat ? chat.title : 'Unknown';
        console.log(`❌ 机器人被移除出 ${chat.type} "${chatTitle}" (ID: ${chat.id})`);
        console.log(`   状态变更: ${old_chat_member.status} → ${new_chat_member.status}`);

        try {
          this.dbUtil.removeGroup(chat.id);

          // 验证删除结果
          const groups = this.dbUtil.getGroups();
          const isRemoved = !groups?.some(group => group.id === chat.id);

          if (isRemoved) {
            console.log(`   ✅ 群组已成功从数据库中移除`);
          } else {
            console.error(`   ❌ 群组移除失败 - 仍在数据库中`);
          }

          // 获取当前所有群组数量
          const totalGroups = groups?.length || 0;
          console.log(`   📊 当前机器人总共在 ${totalGroups} 个群组中`);
        } catch (error) {
          console.error(`   ❌ 移除群组信息时出错:`, error);
        }
      }
    }

    // 其他状态变更（如权限变更等）
    else {
      console.log(`ℹ️  其他状态变更: ${old_chat_member.status} → ${new_chat_member.status}`);

      // 如果是权限变更但机器人仍在群组中，确保群组已记录
      if (
        activeStates.includes(new_chat_member.status) &&
        (chat.type === 'group' || chat.type === 'channel' || chat.type === 'supergroup')
      ) {
        const chatTitle = 'title' in chat ? chat.title : 'Unknown';

        // 检查群组是否已存在于数据库中
        const groups = this.dbUtil.getGroups() || [];
        const groupExists = groups.some(group => group.id === chat.id);

        if (!groupExists) {
          console.log(`⚠️  检测到群组未记录，补充添加: "${chatTitle}" (ID: ${chat.id})`);
          try {
            this.dbUtil.addGroup(chat.id, {
              title: chatTitle || 'Unknown',
              type: chat.type,
              fromId: from.id,
              fromUsername: from.username || '',
            });
            console.log(`   ✅ 群组已补充保存到数据库`);
          } catch (error) {
            console.error(`   ❌ 补充保存群组信息时出错:`, error);
          }
        }
      }
    }
  }

  /**
   * 显示帮助信息 - 列出所有可用命令
   * @param ctx
   */
  handleHelp(ctx: Context) {
    const helpText = `
🤖 **Twitter Bot 帮助**

📱 **基础命令**
• \`/start\` - 启动机器人并显示欢迎信息
• \`/help\` - 显示此帮助信息

👥 **订阅管理命令**
• \`/sub <用户名>\` - 订阅 Twitter 用户
  例如：\`/sub elonmusk\`
• \`/unsub <用户名>\` - 取消订阅 Twitter 用户
  例如：\`/unsub elonmusk\`
• \`/users\` - 查看当前订阅的所有用户列表

📊 **群组管理**
• \`/groups\` - 查看机器人当前所在的群组列表

⚙️ **管理员命令** 🔒
• \`/admin <用户名>\` - 添加管理员
  例如：\`/admin new_admin\`
• \`/admins\` - 查看所有管理员列表
• \`/debug\` - 显示详细的机器人状态和调试信息

📋 **说明**
• 标有 🔒 的命令需要管理员权限
• 推文会自动转发到所有机器人所在的群组
• 第一个添加机器人的用户自动成为管理员

💡 **使用提示**
• 订阅用户名不需要包含 @ 符号
• 机器人支持群组、超级群组和频道
• 使用 \`/groups\` 查看转发目标群组
• 如果群组没有记录，请使用 \`/debug\` 检查状态
    `.trim();

    ctx.reply(helpText, { parse_mode: 'Markdown' });
  }

  /**
   * 列举订阅的用户
   * @returns
   */
  handleUsers(ctx: Context) {
    const text = this.dbUtil.getUsers()?.join('\n');
    if (!text) {
      ctx.reply('暂无订阅用户');
      return;
    }
    ctx.reply(text);
  }

  /**
   * 列举机器人所在的群组
   * @param ctx
   */
  handleGroups(ctx: Context) {
    const groups = this.dbUtil.getGroups();
    if (!groups || groups.length === 0) {
      ctx.reply('机器人当前未加入任何群组');
      return;
    }

    const groupsList = groups
      .map((group, index) => {
        const status =
          group.type === 'supergroup'
            ? '超级群组'
            : group.type === 'group'
              ? '普通群组'
              : group.type === 'channel'
                ? '频道'
                : group.type;
        return `${index + 1}. ${group.title} (${status})\n   ID: ${group.id}`;
      })
      .join('\n\n');

    ctx.reply(`🤖 机器人当前所在群组 (${groups.length}个):\n\n${groupsList}`);
  }

  /**
   * 订阅用户
   * @param ctx
   * @returns
   */
  async handleSub(ctx: Context) {
    try {
      if (!this.isAdmin(ctx.from?.username || '')) {
        ctx.reply(`您不是管理员，没有操作权限，请联系 @${this.dbUtil.getAdmins()?.[0]}`);
        return;
      }

      const userName = ctx.text?.split(' ')[1];
      if (!userName) {
        ctx.reply('请输入用户名');
        return;
      }

      await this.twitterUtil.followUser(userName);
      this.dbUtil.addUser(userName);
      ctx.reply(`已订阅用户 ${userName}`);
    } catch (error) {
      console.error('handleSub error:', error);
      ctx.reply('订阅失败');
    }
  }

  /**
   * 取消订阅用户
   * @param ctx
   * @returns
   */
  handleUnSub(ctx: Context) {
    try {
      if (!this.isAdmin(ctx.from?.username || '')) {
        ctx.reply(`您不是管理员，没有操作权限，请联系 @${this.dbUtil.getAdmins()?.[0]}`);
        return;
      }

      const userName = ctx.text?.split(' ')[1];
      if (!userName) {
        ctx.reply('请输入用户名');
        return;
      }
      this.dbUtil.removeUser(userName);
      ctx.reply(`已取消订阅用户 ${userName}`);
    } catch (error) {
      console.error('handleUnSub error:', error);
      ctx.reply('取消订阅失败');
    }
  }

  /**
   * 添加管理员
   * @param ctx
   */
  handleAdmin(ctx: Context) {
    if (!this.isAdmin(ctx.from?.username || '')) {
      ctx.reply(`您不是管理员，没有操作权限，请联系 @${this.dbUtil.getAdmins()?.[0]}`);
      return;
    }

    const userName = ctx.text?.split(' ')[1];
    if (!userName) {
      ctx.reply('请输入用户名');
      return;
    }
    this.dbUtil.addAdmin(userName);
  }

  /**
   * 列举管理员
   * @param ctx
   */
  handleAdmins(ctx: Context) {
    const text = this.dbUtil.getAdmins()?.join('\n');
    if (!text) {
      ctx.reply('暂无管理员');
      return;
    }
    ctx.reply(text);
  }

  /**
   * 调试信息 - 显示机器人详细状态
   * @param ctx
   */
  handleDebug(ctx: Context) {
    if (!this.isAdmin(ctx.from?.username || '')) {
      ctx.reply(`您不是管理员，没有操作权限，请联系 @${this.dbUtil.getAdmins()?.[0]}`);
      return;
    }

    const groups = this.dbUtil.getGroups() || [];
    const users = this.dbUtil.getUsers() || [];
    const admins = this.dbUtil.getAdmins() || [];

    const debugInfo = [
      '🔧 **机器人调试信息**',
      '',
      `📊 **统计信息:**`,
      `• 群组数量: ${groups.length}`,
      `• 订阅用户: ${users.length}`,
      `• 管理员: ${admins.length}`,
      '',
      `📱 **群组列表:**`,
      groups.length > 0
        ? groups
            .map(
              (group, index) =>
                `${index + 1}. "${group.title}" (${group.type})\n   ID: \`${group.id}\`\n   添加者: ${group.fromUsername ? `@${group.fromUsername}` : `ID:${group.fromId}`}`,
            )
            .join('\n\n')
        : '• 无群组',
      '',
      `👥 **订阅用户:**`,
      users.length > 0 ? users.map(user => `• @${user}`).join('\n') : '• 无订阅用户',
      '',
      `⚙️ **管理员:**`,
      admins.map(admin => `• @${admin}`).join('\n'),
      '',
      `🕒 **当前时间:** ${dayjs().tz('Asia/Shanghai').format('YYYY-MM-DD HH:mm:ss')}`,
      '',
      '💡 **使用说明:**',
      '• 将机器人添加到新群组会自动记录',
      '• 确保机器人有接收群组消息的权限',
      '• 使用 /groups 查看群组列表',
    ].join('\n');

    ctx.reply(debugInfo, { parse_mode: 'Markdown' });
  }

  /**
   * 检查推特更新
   */
  checkUpdate() {
    this.twitterUtil.checkUpdate({
      onUpdate: async tweetData => {
        const groups = this.dbUtil.getGroups() || [];
        const subscribedUsers = this.dbUtil.getUsers() || [];

        const tweet = tweetData.tweet;
        const user = tweetData.user;
        const username = user.legacy.screenName;

        // 只推送订阅的推特用户
        if (!subscribedUsers.includes(username)) {
          return;
        }

        console.log(`📧 收到来自 @${username} 的新推文，准备转发到 ${groups.length} 个群组`);

        const createAt = tweet.legacy?.createdAt;
        const text = [
          `*${user.legacy.name}* 发推了`,
          `内容: ${tweet.legacy?.fullText}`,
          `当前时间: ${dayjs(Date.now()).tz('Asia/Shanghai').format('YYYY-MM-DD HH:mm:ss')}`,
          `北京时间: ${dayjs(createAt).tz('Asia/Shanghai').format('YYYY-MM-DD HH:mm:ss')}`,
          `世界时间: ${dayjs(createAt).utc().format('YYYY-MM-DD HH:mm:ss')}`,
          `链接: https://twitter.com/${username}/status/${tweet.legacy?.idStr}`,
        ].join('\n');

        // 转发到所有机器人所在的群组
        let successCount = 0;
        let failCount = 0;

        for (const group of groups) {
          try {
            await this.bot.telegram.sendMessage(group.id, text, {
              parse_mode: 'Markdown',
            });
            successCount++;
            console.log(`   ✅ 已转发到 "${group.title}" (${group.id})`);
          } catch (error) {
            failCount++;
            console.error(`   ❌ 转发到 "${group.title}" (${group.id}) 失败:`, error);
          }
        }

        console.log(`📊 推文转发完成: 成功 ${successCount} 个，失败 ${failCount} 个`);
      },
    });
  }

  /**
   * 判断是否是管理员
   * @param userName
   * @returns
   */
  isAdmin(userName: string) {
    return this.dbUtil.getAdmins()?.includes(userName);
  }
}
