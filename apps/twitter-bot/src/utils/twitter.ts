import dayjs from 'dayjs';
import {
  TweetApiUtilsData,
  TwitterOpenApi,
  TwitterOpenApiClient,
} from 'twitter-openapi-typescript';
import { twitterApi } from './api';

export interface Config {
  ct0: string;
  authToken: string;
  interval: number;
}

export interface checkUpdateCallback {
  onUpdate?: (tweetData: TweetApiUtilsData) => void;
}

export class TwitterUtil {
  private tweetMap: Map<string, TweetApiUtilsData> = new Map();
  private startTime: number = 0;
  private config!: Config;
  private client!: TwitterOpenApiClient;

  /**
   * 创建服务
   * @param options
   */
  static async create(options: Config) {
    const instance = new TwitterUtil();
    const api = new TwitterOpenApi();
    instance.client = await api.getClientFromCookies({
      ct0: options.ct0,
      auth_token: options.authToken,
    });
    instance.config = options;
    instance.startTime = Date.now();
    return instance;
  }

  /**
   * 检查消息更新
   * @param callback
   */
  async checkUpdate(callback: checkUpdateCallback = {}) {
    try {
      const { onUpdate } = callback;
      const homeLatestTimeline = await this.client.getTweetApi().getHomeLatestTimeline({
        extraParam: {
          features: twitterApi.graphql.HomeLatestTimeline.features,
        },
      });
      const latestTweets = homeLatestTimeline.data.data
        .sort((a, b) => {
          return (
            dayjs(b.tweet.legacy?.createdAt).valueOf() - dayjs(a.tweet.legacy?.createdAt).valueOf()
          );
        })
        .filter(tweetData => dayjs(tweetData.tweet.legacy?.createdAt).valueOf() > this.startTime)
        .filter(tweetData => !this.tweetMap.get(tweetData.tweet.legacy?.idStr || ''))
        .filter(tweetData => !tweetData.promotedMetadata)
        .filter(tweetData => tweetData.tweet.typename === 'Tweet');

      latestTweets.forEach(tweetData => {
        this.tweetMap.set(tweetData.tweet.legacy?.idStr || '', tweetData);
        if (onUpdate) {
          onUpdate(tweetData);
        }
      });

      const randomValue = Math.floor(Math.random() * this.config.interval) + 1;
      const delay = Math.max(randomValue, 3);
      console.log(`Delay for ${delay} seconds...`);
      await new Promise(resolve => {
        setTimeout(resolve, delay * 1000);
      });
    } catch (error) {
      console.error('checkUpdate error:', error);
    } finally {
      console.log('Next checkUpdate...');
      this.checkUpdate(callback).catch(console.error);
    }
  }

  /**
   * 关注用户
   */
  async followUser(screenName: string) {
    const res = await this.client.getUserApi().getUserByScreenName({
      screenName,
    });
    const userId = res.data.user?.restId || '';
    await this.client.getV11PostApi().postCreateFriendships({
      userId,
    });
  }

  /**
   * 取消关注用户
   */
  async unfollowUser(screenName: string) {
    const res = await this.client.getUserApi().getUserByScreenName({
      screenName,
    });
    const userId = res.data.user?.restId || '';
    await this.client.getV11PostApi().postDestroyFriendships({
      userId,
    });
  }
}
