from __future__ import annotations

import json
import logging
from typing import Any, Callable, Coroutine

import aio_pika

logger = logging.getLogger(__name__)


class MessageQueue:
    """
    Clean RabbitMQ wrapper. Connect once at app startup, then publish
    and consume without managing channels or connections in business logic.

    Usage:
        mq = MessageQueue(url="amqp://guest:guest@localhost/")
        await mq.connect()
        await mq.publish("my_queue", {"key": "value"})
        await mq.close()
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None

    async def connect(self) -> None:
        """Open a robust (auto-reconnecting) connection and channel."""
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=1)
        logger.info("RabbitMQ connected: %s", self._url)

    async def publish(self, queue_name: str, message: dict) -> None:
        """Publish a persistent JSON message to a durable queue."""
        if not self._channel:
            raise RuntimeError("MessageQueue is not connected. Call connect() first.")

        await self._channel.declare_queue(queue_name, durable=True)
        body = json.dumps(message).encode()

        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=body,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=queue_name,
        )
        logger.info("Published to %s: %s", queue_name, message)

    async def consume(
        self,
        queue_name: str,
        callback: Callable[[dict[str, Any]], Coroutine],
    ) -> None:
        """
        Start consuming from a durable queue. Blocks indefinitely.

        callback receives parsed dict payloads and should be an async function.
        Messages are acknowledged automatically after callback completes.
        """
        if not self._channel:
            raise RuntimeError("MessageQueue is not connected. Call connect() first.")

        queue = await self._channel.declare_queue(queue_name, durable=True)
        logger.info("Consuming from queue: %s", queue_name)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                # TODO: message.process() auto-acks on success and nacks on exception.
                #       In production, add manual ack with dead-letter queue (DLQ) routing
                #       so permanently failing messages don't block the queue forever.
                async with message.process():
                    payload = json.loads(message.body.decode())
                    logger.info("Received from %s: %s", queue_name, payload)
                    await callback(payload)

    async def close(self) -> None:
        """Gracefully close the connection."""
        if self._connection:
            await self._connection.close()
            logger.info("RabbitMQ connection closed")
