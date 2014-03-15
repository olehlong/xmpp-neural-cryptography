'''
Created on Oct 2, 2013

@author: olehlong
'''

import numpy as np
import hashlib
import json

class TreeParityMachine:
    '''
    Tree parity machine class
    '''


    def __init__(self, iK, iN, iL):
        '''
        Constructor
        '''
        
        self.K = iK # hidden layer size
        self.N = iN # number of input neurons for each hidden neuron 
        self.L = iL # distribution width
        
        self.W = [0] * (self.K * self.N) # input layer
        self.H = [0] * self.K # hidden layer
        
        self.output = None # output
    
    def compute_result(self, X):
        '''
        compute output and hidden layer
        '''
        self.output = 1
        for i in range(self.K):
            summ = 0
            for j in range(self.N):
                summ += self.W[i * self.N + j] * X[i * self.N + j]
            self.H[i] = self.signum(summ)
            self.output *= self.signum(summ)
    
    def update_weights(self, X, outputB):
        '''
        X - input vector
        '''
        for i in range(self.K):
            for j in range(self.N):
                nW = self.W[i * self.N + j] + X[i * self.N + j] * self.equal(self.output, self.H[i]) * self.equal(self.output, outputB)
                if nW > self.L:
                    nW = self.L
                if nW < -self.L:
                    nW = -self.L
                self.W[i * self.N + j] = nW
                
    def update_weights_solo(self, X):
        '''
        X - input vector
        '''
        for i in range(self.K):
            for j in range(self.N):
                nW = self.W[i * self.N + j] + X[i * self.N + j] * self.equal(self.output, self.H[i])
                if nW > self.L:
                    nW = self.L
                if nW < -self.L:
                    nW = -self.L
                self.W[i * self.N + j] = nW
        
    
    def randomize_weights(self):
        '''
        fill self.W with random weights
        '''
        for i in range(len(self.W)):
            # L - (rand() % (2 * L + 1));
            self.W[i] = np.random.randint(-self.L, self.L)
            
    def equal(self, a, b):
        return 1 if a == b else 0
    
    def signum(self, a):
        return 1 if a > 0 else -1
    
def rand_bit():
    return 1 if np.random.randint(2) == 1 else -1
    
def create_vector(k, n):
    res = []
    for i in range(k*n):
        res.append(rand_bit())
    return res
    
    
class TPMManager():
    '''
    TPM manager
    
    You must set recvr (message receiver) and transport object that have method 
        tpm_send(recvr, rvec=None, out=None, w=None, eqout=None, status=None, it=None)
    '''
    
    def __init__(self):
        '''
        init tpm manager
        '''
        
        self.k = 0
        self.n = 0
        self.l = 0
        
        self.dic = "01234567890_abcdefghijklmnopqrstuvwxyz"
        
        self.tpm = None
        
        self.max_iter = 0
        self.curr_iter = 0
        self.fail_count = 0
        self.max_fail = 50
        
        self.recvr = None
        
        self.transport = None
        
        self.prev_vec = None
        
        self.is_success = False
        
        self.__key = None
    
    def init(self, k, n, l):
        '''
        set up tpm
        '''
        self.k = k
        self.n = n
        self.l = l
                
        self.max_iter = l**3*n*k
        # self.max_iter = 10
        
        self.tpm = TreeParityMachine(k, n, l)
        self.tpm.randomize_weights()
        
    def fill(self, k, n, l, w):
        
        self.init(k, n, l)
        
        if len(w) == k*n:
            self.tpm.W = w
            return True
        
        return False
    
    def clear(self):
        self.k = 0
        self.n = 0
        self.l = 0
        self.max_iter = 0
        self.tpm = None
        
    def start_iter(self):
        '''
        begin sync
        '''
        self.__key = None
        
        rvec = self.vect()
        self.tpm.compute_result(rvec)
                
        self.prev_vec = rvec
        
        self.transport.tpm_send(self.recvr, rvec, None, self.tpm.output, status="start", it=0)
        
    def vect(self):
        '''
        get vector for tpm settings
        '''
        return create_vector(self.k, self.n)
    
    def w_sum(self):
        '''
        get hash-sum of weights for comparison
        '''
        return hashlib.md5(json.dumps(self.tpm.W)).hexdigest()
        
    def recv(self, rvec, oout=None, out=None, w=None, eqout=None, status=None, it=None):
        '''
        sync iteration
        
        rvec - random vector
        out - tpm output
        w - hash-sum for another tpm weights
        eqout - outputs equality
        status - process status:
                start
                stage_1
                success
                fail
        it - iteration
        '''
        s_rvec = self.vect()
        
        self.curr_iter = it
                
        if self.curr_iter == self.max_iter:
            self.transport.tpm_send(self.recvr, status="fail")
            return True
        
        if status == "start":
            # stage_1
            print "status: start"
            
            self.tpm.compute_result(rvec)
                        
            self.prev_vec = s_rvec
            
            if self.tpm.output == out:
                print "out equals"
                
                self.tpm.update_weights(rvec, out)
                
                # prepare data for next iteration
                self.tpm.compute_result(s_rvec)
                self.transport.tpm_send(self.recvr, s_rvec, out, self.tpm.output, self.w_sum(), True, "stage_1", it+1)
                
            else:
                
                self.fail_count += 1
                
                if self.fail_count == self.max_fail:
                    self.transport.tpm_send(self.recvr, status="fail")
                else:
                    # prepare data for next iteration
                    self.tpm.compute_result(s_rvec)
                    self.transport.tpm_send(self.recvr, s_rvec, None, self.tpm.output, self.w_sum(), False, "stage_1", it+1)
            return True
        elif status == "stage_1":
            print "status: stage_1"
            
            if eqout:
                print "eqout"
                
                self.fail_count = 0
                
                self.tpm.update_weights(self.prev_vec, oout) # need old rvec
                
                m_w = self.w_sum()
                if m_w == w:
                    print "success from manager"
                    
                    self.is_success = True
                    
                    self.transport.tpm_send(self.recvr, status="success")
                    
                    return True
                else:
                    print m_w, " != ", w
            
            self.tpm.compute_result(rvec)
            
            self.prev_vec = s_rvec
            
            if self.tpm.output == out:
                self.tpm.update_weights(rvec, out)
                
                # prepare data for next iteration
                self.tpm.compute_result(s_rvec)
                self.transport.tpm_send(self.recvr, s_rvec, out, self.tpm.output, self.w_sum(), True, "stage_1", it+1)
                
            else:
                self.fail_count += 1
                
                if self.fail_count == self.max_fail:
                    self.transport.tpm_send(self.recvr, status="fail")
                else:
                    # prepare data for next iteration
                    self.tpm.compute_result(s_rvec)
                    self.transport.tpm_send(self.recvr, s_rvec, None, self.tpm.output, self.w_sum(), False, "stage_1", it+1)
            return True
            
            
                    
        else:
            print "Something went wrong"
            
    def get_key(self):
        if self.__key != None:
            return self.__key
        
        key = ""
        key_size = 37/(self.tpm.L*2 + 1)
        key_length = self.tpm.K * self.tpm.N / key_size
        
        for i in range(1, key_length+1):
            k=1
            for j in range((i-1)*key_size, i*key_size):
                k += self.tpm.W[j] + self.tpm.L
            key += self.dic[k]
        self.__key = key
        
        return key
    
    def get_data(self):
        return {'w': self.tpm.W, 'k': self.tpm.K, 'n': self.tpm.N, 'l': self.tpm.L}

        
        
        
        
    
    
