#!/usr/bin/env python
"""
worker daemon

"""
import signal
from time import sleep
import pika
import sys


class Worker(object):
    INPUT_QUEUE_NAME = 'in_queue'

    def __init__(self):
        self.connect()
        signal.signal(signal.SIGTERM, self.exit)

    def exit(self, signal=None, frame=None):
        self.input_channel.close()
        self.output_channel.close()
        self.connection.close()
        sys.exit(0)

    def connect(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.output_channel = self.connection.channel()
        self.input_channel = self.connection.channel()

        self.input_channel.exchange_declare(exchange='tornado_input', exchange_type='topic')
        self.input_channel.queue_declare(queue=self.INPUT_QUEUE_NAME)
        self.input_channel.queue_bind(exchange='tornado_input', queue=self.INPUT_QUEUE_NAME)

    def run(self):
        """
        self.input_channel.basic_consume(on_message_callback=self.handle_message,
                                         queue=self.INPUT_QUEUE_NAME,
                                         no_ack=True)
        """
        self.input_channel.basic_consume(on_message_callback=self.handle_message,
                                         queue=self.INPUT_QUEUE_NAME, auto_ack=True)
        try:
            self.input_channel.start_consuming()
        except (KeyboardInterrupt, SystemExit):
            print(" Exiting")
            self.exit()

    def handle_message(self, ch, method, properties, body):
        """
        this is a pika.basic_consumer callback
        handles client inputs, runs appropriate methods

        Args:
            ch: amqp channel
            method: amqp method
            properties:
            body: message body
        """
        sess_id = method.routing_key
        self.worker(sess_id)
        if self.connection.is_closed:
            print("Connection is closed, re-opening...")
            self.connect()
        print("---------- %s %s" % (sess_id, body))
        self.output_channel.basic_publish(exchange='',
                                          routing_key=sess_id,
                                          body=body)

    def worker(self, sess_id):
        # you can do your actual work here
        pass


def manage_processes():
    import atexit, os, subprocess, signal

    global child_pids
    child_pids = []
    no_subprocess = [arg.split('manage=')[-1] for arg in sys.argv if 'manage' in arg][0]
    print("starting %s workers" % no_subprocess)
    for i in range(int(no_subprocess)):
        proc = subprocess.Popen([sys.executable, __file__],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        child_pids.append(proc.pid)
        print("Started worker with pid %s" % proc.pid)

    def kill_child():
        for pid in child_pids:
            if pid is not None:
                os.kill(pid, signal.SIGTERM)

    atexit.register(kill_child)
    while 1:
        try:
            sleep(1)
        except KeyboardInterrupt:
            print("Keyboard interrupt, exiting")
            sys.exit(0)


if __name__ == '__main__':
    if 'manage' in str(sys.argv):
        manage_processes()
    else:
        
        worker = Worker()
        worker.run()
