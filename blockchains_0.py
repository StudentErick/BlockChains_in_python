import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4
import requests

from flask import Flask, jsonify, request


class BlockChains(object):
    def __init__(self):
        self.current_transactions = []  # 当前区块的交易
        self.chain = []  # 区块链
        self.new_block(previous_hash=1, proof=100)  # 产生创世区块
        self.nodes = set()  # 区块链中的结点，防止重复结点的出现

    def register_node(self, address):
        '''
        在区块链中添加新的结点
        :param address: <str>结点的地址，格式为'http://192.168.0.5:5000'
        :return: None
        '''
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)  # 自动忽略已经存在的结点

    def new_block(self, proof, previous_hash=None):
        '''
        生成新的区块
        :param proof:
        :param previous_hash:  前一个区块的哈希值
        :return: <dict> 新的区块
        '''
        s = str(previous_hash).encode('utf-8')
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': s or self.hash(self.chain[-1])
        }

        self.current_transactions = []
        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        '''
        生成新的交易信息，信息将加入下一个待挖掘的区块中
        :param sender: 发送方
        :param recipient: 接收方
        :param amount: 比特币数目
        :return: <int> 区块的索引
        '''
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })
        return self.last_block['index'] + 1

    @property
    def last_block(self):
        return self.chain[-1]  # 返回最后一个区块

    @staticmethod
    def hash(block):

        '''
        生成区块的SHA-256哈希值
        :param block: <Block>当前区块的哈希值
        :return: <str>
        '''
        block_string = json.dumps(block, sort_keys=True)
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_proof):

        '''
        寻找一个p，使得与前一个区块proof哈希后的数值有4个0开头
        :param last_proof: <int>
        :return: <int>
        '''
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        '''
        验证是否以4个0开头
        :param last_proof: 上一个区块的proof
        :param proof: 当前的proof
        :return: <bool>
        '''
        guess = (str(last_proof) + str(proof)).encode()  # 相当于一个字符串的拼接
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def valid_chain(self, chain):
        '''
        判断当前的区块链是否是有效的，检查
        :param chain: <list>一个区块链的列表
        :return: <bool>
        '''
        last_block = chain[0]
        current_index = 1

        # 从前往后，逐个检查区块的合理性
        while current_index < len(chain):
            block = chain[current_index]
            print(str(last_block))
            print(str(block))
            print("\n-----------\n")
            # 检查区块的哈希值是否正确
            if block['previous_hash'] != self.hash(last_block):
                return False
            # 检查工作量证明是否是正确的
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conclicts(self):
        '''
        检查区块链的冲突，必须是选择网络中最长的区块链
        :return:<bool> True如果当前链被取代，否则False
        '''
        neighbours = self.nodes  # 获取所有的邻接结点的消息
        new_chain = None

        max_length = len(self.chain)

        for node in neighbours:
            s = str(node)
            st = 'http://' + s + '/chain'
            response = requests.get(st)

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # 检查区块链的合法性
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # 决定是否替换
        if new_chain:
            self.chain = new_chain
            return True
        return False


app = Flask(__name__)  # 初始化结点
node_identifier = str(uuid4()).replace('-', '')  # 为每一个结点生成唯一的编号
blockchain = BlockChains()  # 初始化区块链


@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # 给工作量证明的结点提供奖励，"0"表示新挖出的比特币
    blockchain.new_transaction(sender='0', recipient=node_identifier, amount=1)

    block = blockchain.new_block(proof)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
    s = str(index)
    response = {'message': 'Transaction will be added to Block' + s}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
