# -*-  coding: utf-8 -*-
import logging
import pika
import time
from pika.adapters.tornado_connection import TornadoConnection
pika.log = logging.getLogger(__name__)


class PikaClient(object):
    INPUT_QUEUE_NAME = 'in_queue'
    def __init__(self, io_loop):
        self.io_loop = io_loop
        self.received_message_counter = 0
        self.sent_message_counter = 0
        self.start_time = -1
        self.connected = False
        self.connecting = False
        self.connection = None
        self.in_channel = None
        self.out_channels = {}
        self.websockets = {}
        self.connect()

    def connect(self):
        if self.connecting:
            return
        self.connecting = True
        
        cred = pika.PlainCredentials('guest', 'guest')
        param = pika.ConnectionParameters(
            host='127.0.0.1',
            port=5672,
            virtual_host='/',
            credentials=cred
        )
        
        
        #param = pika.URLParameters('amqp://guest:guest@localhost:5672/%2F')

        self.connection = TornadoConnection(param,
                                            on_open_callback=self.on_connected)

    def on_connected(self, connection):
        self.connected = True
        self.connection = connection
        self.in_channel = self.connection.channel(on_open_callback=self.on_conn_open)

    def on_conn_open(self, channel):
        self.in_channel.exchange_declare(exchange='tornado_input', exchange_type='topic')
        channel.queue_declare(callback=self.on_input_queue_declare, queue=self.INPUT_QUEUE_NAME)

    def on_input_queue_declare(self, queue):
        self.in_channel.queue_bind(callback=None,
                           exchange='tornado_input',
                           queue=self.INPUT_QUEUE_NAME,
                           routing_key="#")

    def register_websocket(self, sess_id, ws):
        self.websockets[sess_id] = ws
        channel = self.create_out_channel(sess_id)
        


    def unregister_websocket(self, sess_id):
        del self.websockets[sess_id]
        if sess_id in self.out_channels:
            self.out_channels[sess_id].close()
        print("Time: %s, In: %s Out: %s" % (int(time.time() - self.start_time),
                                                  self.received_message_counter,
                                                  self.sent_message_counter) )


    def create_out_channel(self, sess_id):
        def on_output_channel_creation(channel):
            def on_output_queue_decleration(queue):
                channel.basic_consume(on_message_callback=self.on_message, queue=sess_id)
            self.out_channels[sess_id] = channel
            channel.queue_declare(callback=on_output_queue_decleration,
                                  queue=sess_id,
                                  auto_delete=True,
                                  exclusive=True)

        self.connection.channel(on_open_callback=on_output_channel_creation)


    def redirect_incoming_message(self, sess_id, message):
        if not self.sent_message_counter:
            self.start_time = time.time()
        self.received_message_counter += 1
        if not self.received_message_counter % 1000:
            print("Total Received: %s " % self.received_message_counter)
        #print("1111111111111111 %s  %s" % (sess_id, message))
        self.in_channel.basic_publish('tornado_input',
                              sess_id,
                              message)

    def on_message(self, channel, method, header, body):
        self.sent_message_counter += 1
        sess_id = method.routing_key
        if sess_id in self.websockets:
            print("3333333333333 %s %s" % (sess_id, body))
            self.websockets[sess_id].write_message(body)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        else:
            print("222222222222 %s" % body)
            channel.basic_reject(delivery_tag=method.delivery_tag)


