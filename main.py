#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Created on Oct 2, 2013

@author: gaolong
'''
from client.GLChat import GLChatView

from nc.TreeParityMachine import TreeParityMachine, create_vector, TPMManager

import logging

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)-8s %(message)s') 
    
    clist = GLChatView()
    clist.start_client()
    clist.main()
    
if __name__ == '__main__':
    main()
