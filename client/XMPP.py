'''
Created on Oct 3, 2013

@author: olehlong
'''
import sleekxmpp

from sleekxmpp.xmlstream import ElementBase
from sleekxmpp.stanza import Iq
from sleekxmpp.exceptions import XMPPError
from sleekxmpp.xmlstream import register_stanza_plugin
from sleekxmpp.xmlstream.handler import Callback
from sleekxmpp.xmlstream.matcher import StanzaPath

import sqlite3

import os
from os.path import dirname, expanduser

import json
import time

class SyncAction(ElementBase):
    """
    A stanza class for XML content of the form:

    <sync xmlns="sleekxmpp:custom:sync">
      <rvec></rvec>
      <out></out>
      <w></w>
      <eqout></eqout>
      <it></it>
      <status></status>
    </sync>
    """
    
    name = 'sync'
    namespace = 'sync'
    
    plugin_attrib = 'sync'
    
    interfaces = set(('rvec', 'oout', 'out', 'w', 'eqout', 'status', 'it'))
    sub_interfaces = interfaces
    
class ConfirmSyncAction(ElementBase):
    """
    A stanza class for XML content of the form:

    <confirmsync xmlns="sleekxmpp:custom:confirmsync">
      <k></k>
      <n></n>
      <l></l>
      <status></status>
    </confirmsync>
    """
    
    name = 'confirmsync'
    namespace = 'confirmsync'
    
    plugin_attrib = 'confirmsync'
    
    interfaces = set(('status', 'k', 'n', 'l'))
    sub_interfaces = interfaces
    
class ChangeModeAction(ElementBase):
    """
    A stanza class for XML content of the form:

    <changemode xmlns="sleekxmpp:custom:changemode">
      <key></key>
      <val></val>
    </changemode>
    """
    
    name = 'changemode'
    namespace = 'changemode'
    
    plugin_attrib = 'changemode'
    
    interfaces = set(('key', 'val'))
    sub_interfaces = interfaces

class XMPPClient(sleekxmpp.ClientXMPP):
    '''
    classdocs
    '''

    def __init__(self, jid, password, storage, status = "available", status_msg = ""):
        '''
        Constructor
        '''
        super(XMPPClient, self).__init__(jid, password)
        
        self._start_status = status
        self._start_status_msg = status_msg
        
        
        self.allow_subscription = True
        
        self.store = storage
        
        self.roster.set_backend(self.store)
        
        register_stanza_plugin(Iq, SyncAction)
        register_stanza_plugin(Iq, ConfirmSyncAction)
        register_stanza_plugin(Iq, ChangeModeAction)
        
        self.register_plugin('xep_0004') # Data Forms
        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0050') # Adhoc Commands
        self.register_plugin('xep_0059') # Result Set Management
        self.register_plugin('xep_0060') # Publish/Subscribe (PubSub)
        self.register_plugin('xep_0086') 
        self.register_plugin('xep_0199') # XMPP Ping
        
        self.register_handler(Callback('Sync iq', StanzaPath('iq/sync'), self._handle_sync))
        self.register_handler(Callback('Sync confirm iq', StanzaPath('iq/confirmsync'), self._handle_confirm_sync))
        self.register_handler(Callback('Change mode', StanzaPath('iq/changemode'), self._handle_change_mode))
        # self.add_event_handler('sync_action', self.recv_sync)
        
        self.add_event_handler('session_start', self.evt_start)
        self.add_event_handler('presence_subscribe', self.evt_subscribe)
        self.add_event_handler('presence_subscribed', self.evt_subscribed)
        
        self.add_event_handler('presence_unsubscribe', self.evt_unsubscribe)
        self.add_event_handler('presence_unsubscribed', self.evt_unsubscribed)
        
        # self.add_event_handler('presence_probe', self._presence_probe)
        self.add_event_handler('pubsub_subscription', self.evt_subscription)
          
    def subscribe_buddy(self, jid):
        self.send_presence(pto=jid, ptype='subscribe')
        
    def unsubscribe_buddy(self, jid):
        self.send_presence(pto=jid, ptype='unsubscribe')
        
    def remove_buddy(self, jid):
        try:
            self.update_roster(jid, subscription='remove')
        except:
            print "no roster"
            
        self.store.remove(self.boundjid.bare, jid)
    
    def rename_buddy(self, jid, name):
        name = unicode(name, "utf-8")
        try:
            self.update_roster(jid, name=name)
        except:
            print "no roster"
          
    def _handle_sync(self, iq):
        """
        Raise an event for the stanza so that it can be processed in its
        own thread without blocking the main stanza processing loop.
        """
        
        self.event('sync_action', iq)
        
    def _handle_confirm_sync(self, iq):
        print "Conf recv" 
        self.event('confirm_sync_action', iq)
        
    def _handle_change_mode(self, iq):
        self.event('change_mode_action', iq)
                
    def evt_start(self, event):
        print "start"
        self.get_roster()
        self.send_presence(pstatus=self._start_status_msg, pshow=self._start_status)
        
        
    def evt_subscription(self, msg):
        """Handle receiving a node subscription event."""
        print "_subscription"
        print msg
        
    def evt_subscribe(self, presence):
        print "_subscribe"
        # If the subscription request is rejected.
        if not self.allow_subscription:
            self.send_presence(pto=presence['from'], ptype='unsubscribed')
            return
        
        # If the subscription request is accepted.
        self.send_presence(pto=presence['from'], ptype='subscribed')

        # Save the fact that a subscription has been accepted, somehow. Here
        # we use a backend object that has a roster.
        self.client_roster.subscribe(presence['from'])
        # self.backend.roster.subscribe(presence['from'])

        # If a bi-directional subscription does not exist, create one.
        #if not self.client_roster.roster.sub_from(presence['from']):
        #    self.sendPresence(pto=presence['from'], ptype='subscribe')
        if not self.client_roster[presence['from']]['from']:
            self.sendPresence(pto=presence['from'], ptype='subscribe')
        
        
        
    def evt_subscribed(self, presence):
        print "_subscribed"
        
        self.client_roster[presence['from']].authorize()
        
        self.event('subscription_finished', presence)
        
        
    def evt_unsubscribe(self, presence):
        print "unsubscribe"
        print presence
        
        self.event('unsubscribe', presence)
        
    def evt_unsubscribed(self, presence):
        print "unsubscribed"
        print presence
        
    def tpm_send(self, recvr, rvec=None, oout=None, out=None, w=None, eqout=None, status=None, it=None):
        
        out_rvec = rvec if rvec is None else json.dumps(rvec)
        # out_w = w if w is None else json.dumps(w)
        
        iq = self.Iq()
        iq['to'] = recvr
        iq['from'] = self.boundjid
        iq['type'] = 'set'
        
        iq['sync']['rvec'] = out_rvec
        iq['sync']['oout'] = json.dumps(oout)
        iq['sync']['out'] = json.dumps(out)
        iq['sync']['w'] = w
        iq['sync']['eqout'] = json.dumps(eqout)
        iq['sync']['status'] = status
        iq['sync']['it'] = json.dumps(it)
        
        try:
            resp = iq.send(block=False)
        except XMPPError:
            print "error"
            
    def tpm_confirm_send(self, recvr, status=None, k=None, n=None, l=None):
        iq = self.Iq()
        iq['to'] = recvr
        iq['from'] = self.boundjid
        iq['type'] = 'set'
        
        iq['confirmsync']['k'] = str(k)
        iq['confirmsync']['n'] = str(n)
        iq['confirmsync']['l'] = str(l)
        iq['confirmsync']['status'] = status
        
        try:
            resp = iq.send(block=False)
        except XMPPError:
            print "error"
        
    def change_mode_send(self, recvr, key=None, val=None):
        iq = self.Iq()
        iq['to'] = recvr
        iq['from'] = self.boundjid
        iq['type'] = 'set'
        
        iq['changemode']['key'] = str(key)
        iq['changemode']['val'] = json.dumps(val)
        
        try:
            resp = iq.send(block=False)
        except XMPPError:
            print "error"
        
        
class SQLLiteStorage:
    
    def __init__(self):
        #dbfile = os.path.join(dirname(__file__), "../resources/storage.db")
        dbfile = os.path.join(expanduser("~"), ".config/glchat/storage.db")
        
        if not os.path.isfile(dbfile):
            self.create_db(dbfile)
        
        self.conn = sqlite3.connect(dbfile, check_same_thread = False)
        self.conn.row_factory = self.dict_factory
        self.cursor = self.conn.cursor()
        
    def dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d  

    def create_db(self, fn):
        d = os.path.dirname(fn)
        if not os.path.exists(d):
            os.makedirs(d)
            
        self.conn = sqlite3.connect(fn, check_same_thread = False)
        self.conn.row_factory = self.dict_factory
        self.cursor = self.conn.cursor()
        
            
        query = 'CREATE TABLE accounts ( \
                "id" INTEGER PRIMARY KEY, \
                "jid" VARCHAR(128), \
                "password" VARCHAR(128), \
                "auto_connect" BOOLEAN, \
                "status" VARCHAR(16), \
                "status_message" VARCHAR(128) \
                ); \
CREATE TABLE "buddies" ( \
    "id" INTEGER PRIMARY KEY, \
    "jid" VARCHAR(128), \
    "name" VARCHAR(128), \
    "from" BOOLEAN, \
    "to" BOOLEAN, \
    "pending_out" BOOLEAN, \
    "pending_in" BOOLEAN, \
    "subscription" VARCHAR( 128 ), \
    "whitelisted" BOOLEAN, \
    "account_id" INTEGER NOT NULL, \
CHECK ("from" IN (0, 1)), \
CHECK ("to" IN (0, 1)), \
CHECK ("pending_out" IN (0, 1)), \
CHECK ("pending_in" IN (0, 1)), \
CHECK ("whitelisted" IN (0, 1)), \
FOREIGN KEY("account_id") REFERENCES "accounts" ("id") \
);  \
CREATE TABLE groups ( \
    "id" INTEGER PRIMARY KEY, \
    "name" VARCHAR(128), \
    "account_id" INTEGER NOT NULL \
); \
CREATE TABLE buddy_group ( \
    "buddy_id" INTEGER NOT NULL, \
    "group_id" INTEGER NOT NULL \
); \
CREATE TABLE "history" ( \
    "id" INTEGER PRIMARY KEY, \
    "buddy_id" INTEGER NOT NULL, \
    "account_id" INTEGER NOT NULL, \
    "message" TEXT, \
    "is_account" BOOLEAN, \
    "date" INTEGER, \
CHECK ("is_account" IN (0, 1)), \
FOREIGN KEY("buddy_id") REFERENCES "buddies" ("id"), \
FOREIGN KEY("account_id") REFERENCES "accounts" ("id") \
); \
CREATE TABLE "tpms" ( \
    "id" INTEGER PRIMARY KEY, \
    "account_id" INTEGER NOT NULL, \
    "buddy_id" INTEGER NOT NULL, \
    "data" TEXT, \
    "permanent" BOOLEAN, \
CHECK ("permanent" IN (0, 1)), \
FOREIGN KEY("buddy_id") REFERENCES "buddies" ("id") \
);'
        
        self.cursor.executescript(query)
        self.conn.commit()
                
        self.conn.close()
    
    def plugin_init(self):
        pass
        
    def load(self, owner_jid, jid, db_state):
        
        self.cursor.execute("SELECT b.* FROM buddies as b INNER JOIN accounts as a ON(a.id=b.account_id) WHERE b.jid=? AND a.jid=?", (jid, owner_jid,))
        resp = self.cursor.fetchone()
        
        if resp:
            result = {}
            result['name'] = resp['name']
            result['groups'] = []
            result['from'] = True if resp['from'] == 1 else False
            result['to'] = True if resp['to'] == 1 else False
            result['pending_out'] = True if resp['pending_out'] == 1 else False
            result['pending_in'] = True if resp['pending_in'] == 1 else False
            result['whitelisted'] = True if resp['whitelisted'] == 1 else False
            result['subscription'] = resp['subscription']        
            return result
        else:
            return None        
        
        
    def remove(self, owner_jid, jid):
        
        self.cursor.execute("SELECT id FROM accounts WHERE jid=?", (owner_jid,))
        acc = self.cursor.fetchone()
        
        self.cursor.execute("DELETE FROM buddies WHERE jid=? AND account_id=?", (jid, acc['id']))
        self.conn.commit()
        
        
    def save(self, owner_jid, jid, item_state, db_state):
        
        self.cursor.execute("SELECT id FROM accounts WHERE jid=?", (owner_jid,))
        acc = self.cursor.fetchone()
        
        self.cursor.execute("SELECT id FROM buddies WHERE jid=? AND account_id=?", (jid, acc['id']))
        chk = self.cursor.fetchone()
        
        if chk:
            self.cursor.execute("UPDATE buddies SET `name`=?, `from`=?, `to`=?, `pending_out`=?, `pending_in`=?, `subscription`=?, `whitelisted`=? WHERE `id`=?", 
                                (item_state['name'], item_state['from'], item_state['to'], item_state['pending_out'], item_state['pending_in'], item_state['subscription'], item_state['whitelisted'], chk['id']))
        else:
            self.cursor.execute("INSERT INTO buddies(`id`, `jid`, `name`, `from`, `to`, `pending_out`, `pending_in`, `subscription`, `whitelisted`, `account_id`) VALUES(NULL,?,?,?,?,?,?,?,?,?)", 
                                (jid, item_state['name'], item_state['from'], item_state['to'], item_state['pending_out'], item_state['pending_in'], item_state['subscription'], item_state['whitelisted'], acc['id']))
        
        self.conn.commit()
        
    def entries(self, owner_jid, db_state=None):
        """
        Return all roster item JIDs for a given JID.
        """
        if owner_jid is None:
            self.cursor.execute("SELECT jid FROM accounts")
            return [itm['jid'] for itm in self.cursor.fetchall()]
        else:
            self.cursor.execute("SELECT b.jid FROM buddies as b \
                                 INNER JOIN accounts as a ON(a.id=b.account_id) \
                                 WHERE a.jid=?", (owner_jid,))
            return [itm['jid'] for itm in self.cursor.fetchall()]
        
    def get_account_by_JID(self, jid):
        self.cursor.execute("SELECT * FROM accounts WHERE jid=?", (jid,))
        return self.cursor.fetchone()
    
    def add_account(self, jid, password, auto_connect):
        self.cursor.execute("INSERT INTO accounts(id, jid, password, auto_connect, status, status_message) VALUES(NULL,?,?,?,'available','')", (jid, password, auto_connect))
        self.conn.commit()
        
    def set_status(self, aid, status, status_msg):
        status_msg = unicode(status_msg, "utf-8")
        self.cursor.execute("UPDATE accounts SET `status`=?, `status_message`=? WHERE `id`=?", 
                                (status, status_msg, aid))
        self.conn.commit()
        
    def change_account_data(self, aid, password, auto_connect):
        self.cursor.execute("UPDATE accounts SET `auto_connect`=0 WHERE 1=1")
        self.cursor.execute("UPDATE accounts SET `auto_connect`=?, `password`=? WHERE `id`=?", 
                                (auto_connect, password, aid))
        self.conn.commit()
        
    def disable_all_auto_conn(self):
        self.cursor.execute("UPDATE accounts SET `auto_connect`=0 WHERE 1=1")
        self.conn.commit()
        
        
    def get_accounts(self):
        self.cursor.execute("SELECT * FROM accounts")
        return self.cursor.fetchall()
    
    def get_account(self):
        self.cursor.execute("SELECT * FROM accounts WHERE `auto_connect`=1")
        return self.cursor.fetchone()
        
    def get_tpm(self, buddy_jid):
        self.cursor.execute("SELECT t.* FROM tpms as t INNER JOIN buddies as b ON(t.buddy_id=b.id) WHERE b.jid=?", (buddy_jid,))
        res = self.cursor.fetchone()
        
        if res:
            return {'data': json.loads(res['data']), 'permanent': res['permanent']}
        else:
            return None
    
    def set_tpm(self, acc_id, buddy_jid, data, is_permanent):        
        self.cursor.execute("SELECT id FROM buddies WHERE jid=? AND account_id=?", (buddy_jid, acc_id))
        buddy = self.cursor.fetchone()
        
        if not buddy:
            return
        
        self.cursor.execute("SELECT t.id FROM tpms as t INNER JOIN buddies as b ON(t.buddy_id=b.id) WHERE b.jid=?", (buddy_jid,))
        chk = self.cursor.fetchone()
        
        enc_data = json.dumps(data)
        
        if chk:
            self.cursor.execute("UPDATE tpms SET `data`=?, `permanent`=? WHERE `id`=?", 
                                (enc_data, is_permanent, chk['id']))
        else:
            self.cursor.execute("INSERT INTO tpms(`id`, `account_id`, `buddy_id`, `data`, `permanent`) VALUES(NULL,?,?,?,?)", 
                                (acc_id, buddy['id'], enc_data, is_permanent))
            
        self.conn.commit()
        
    def remove_tpm(self, acc_id, buddy_jid):
        self.cursor.execute("SELECT id FROM buddies WHERE jid=? AND account_id=?", (buddy_jid, acc_id))
        buddy = self.cursor.fetchone()
        
        if not buddy:
            return
        
        self.cursor.execute("DELETE FROM tpms WHERE account_id=? AND buddy_id=?", (acc_id, buddy['id']))
        self.conn.commit()
        
        
    def add_history(self, acc_id, buddy_jid, message, is_account):
        
        self.cursor.execute("SELECT id FROM buddies WHERE jid=? AND account_id=?", (buddy_jid, acc_id))
        buddy = self.cursor.fetchone()
        
        if not buddy:
            return
        
        is_acc = 1 if is_account else 0
        date = int(time.time())
        
        message = unicode(message, "utf-8")
        
        self.cursor.execute("INSERT INTO history(id, account_id, buddy_id, message, is_account, date) VALUES(NULL,?,?,?,?,?)", (acc_id, buddy['id'], message, is_acc, date))
        self.conn.commit()
        
    def get_history(self, acc_id, jid):
        self.cursor.execute("SELECT h.* FROM history as h INNER JOIN accounts as a ON(a.id=h.account_id) INNER JOIN buddies as b ON(b.id=h.buddy_id) WHERE a.id=? AND b.jid=? ORDER BY date", (acc_id, jid))
        return self.cursor.fetchall()
    
    def clear_history(self, acc_id, jid):
        
        self.cursor.execute("SELECT id FROM buddies WHERE jid=? AND account_id=?", (jid, acc_id))
        buddy = self.cursor.fetchone()
        
        if not buddy:
            return
                
        self.cursor.execute("DELETE FROM history WHERE account_id=? AND buddy_id=?", (acc_id, buddy['id']))
        self.conn.commit()
        
        
        
        
    

    
    
    
