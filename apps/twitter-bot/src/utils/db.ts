import fs from 'fs';
import path from 'path';

interface Group {
  id: number;
  title: string;
  type: string;
  fromId: number;
  fromUsername: string;
}

export class DBUtil {
  dbPath: string;
  db: {
    groups?: Array<Group>;
    /**
     * 订阅用户列表（推特用户名）
     */
    subUsers?: Array<string>;
    /**
     * 管理员列表（tg用户名）
     */
    admins?: Array<string>;
  };

  constructor() {
    this.dbPath = path.resolve(process.cwd(), 'db.json');
    this.db = this.load();
  }

  load() {
    return JSON.parse(fs.readFileSync(this.dbPath, 'utf8'));
  }

  save() {
    fs.writeFileSync(this.dbPath, JSON.stringify(this.db, null, 2), 'utf8');
  }

  addGroup(id: number, info: Omit<Group, 'id'>) {
    const groups = this.db.groups || [];
    if (groups.every(group => group.id !== id)) {
      this.db.groups = [...groups, { id, ...info }];
      this.save();
    }
  }

  removeGroup(id: number) {
    this.db.groups = this.db.groups?.filter(group => group.id !== id);
    this.save();
  }

  addUser(username: string) {
    const users = this.db.subUsers || [];
    if (!users.includes(username)) {
      this.db.subUsers = [...users, username];
      this.save();
    }
  }

  removeUser(username: string) {
    this.db.subUsers = this.db.subUsers?.filter(user => user !== username);
    this.save();
  }

  addAdmin(id: string) {
    const admins = this.db.admins || [];
    if (!admins.includes(id)) {
      this.db.admins = [...admins, id];
      this.save();
    }
  }

  removeAdmin(id: string) {
    this.db.admins = this.db.admins?.filter(admin => admin !== id);
    this.save();
  }

  getAdmins() {
    return this.db.admins;
  }

  getUsers() {
    return this.db.subUsers;
  }

  getGroups() {
    return this.db.groups;
  }
}
