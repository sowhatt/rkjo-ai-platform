"""Fault probe only: run the delivered consumer, pause after commit before ACK.

No factory, handler, persistence or broker is replaced. The parent kills this
process after observing SQL commit, forcing RabbitMQ's real unacked redelivery.
"""
import os
from pathlib import Path
import runpy
import time
import pika

original = pika.adapters.blocking_connection.BlockingChannel.basic_ack


def pause_before_ack(self, *args, **kwargs):
    Path(os.environ["L1_ACK_BARRIER"]).write_text("handler returned; ACK not sent")
    while True:
        time.sleep(0.1)


pika.adapters.blocking_connection.BlockingChannel.basic_ack = pause_before_ack
runpy.run_module("rkjo_worker.workflow_result_consumer", run_name="__main__")
