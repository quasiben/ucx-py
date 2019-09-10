import pickle
import asyncio
import pytest
import sys
from contextlib import asynccontextmanager

import ucp

msg_sizes = [2 ** i for i in range(0, 25, 4)]
dtypes = ["|u1", "<i8", "f8"]


def make_echo_server(create_empty_data=None):
    """
    Returns an echo server that calls the function `create_empty_data(nbytes)` 
    to create the data container. If None, it uses `np.empty(size, dtype=np.uint8)`
    """
    import numpy as np

    if create_empty_data is None:
        create_empty_data = lambda n: np.empty(n, dtype=np.uint8)

    async def echo_server(ep):
        """
        Basic echo server for sized messages.
        We expect the other endpoint to follow the pattern::
        >>> await ep.send(msg_size, np.uint64().nbytes)  # size of the real message (in bytes)
        >>> await ep.send(msg, msg_size)       # send the real message
        >>> await ep.recv(responds, msg_size)  # receive the echo
        """
        msg_size = np.empty(1, dtype=np.uint64)
        await ep.recv(msg_size)
        msg = create_empty_data(msg_size[0])
        await ep.recv(msg)
        await ep.send(msg)

    return echo_server


def handle_exception(loop, context):
    # context["message"] will always be there; but context["exception"] may not
    msg = context.get("exception", context["message"])
    print(msg)
    sys.exit(-1)


@pytest.mark.asyncio
@pytest.mark.parametrize("size", msg_sizes)
@pytest.mark.parametrize("dtype", dtypes)
async def test_send_recv_numpy(size, dtype):
    asyncio.get_running_loop().set_exception_handler(handle_exception)
    np = pytest.importorskip("numpy")

    msg = np.arange(size, dtype=dtype)
    msg_size = np.array([msg.nbytes], dtype=np.uint64)

    listener = ucp.create_listener(make_echo_server())
    client = await ucp.create_endpoint(ucp.get_address(), listener.port)
    await client.send(msg_size)
    await client.send(msg)
    resp = np.empty_like(msg)
    await client.recv(resp)
    np.testing.assert_array_equal(resp, msg)


@pytest.mark.asyncio
@pytest.mark.parametrize("size", msg_sizes)
@pytest.mark.parametrize("dtype", dtypes)
async def test_send_recv_cupy(size, dtype):
    asyncio.get_running_loop().set_exception_handler(handle_exception)
    np = pytest.importorskip("numpy")
    cupy = pytest.importorskip("cupy")

    msg = cupy.arange(size, dtype=dtype)
    msg_size = np.array([msg.nbytes], dtype=np.uint64)

    listener = ucp.create_listener(make_echo_server(lambda n: cupy.empty((n,), dtype=np.uint8)))
    client = await ucp.create_endpoint(ucp.get_address(), listener.port)
    await client.send(msg_size)
    await client.send(msg)
    resp = cupy.empty_like(msg)
    await client.recv(resp)
    np.testing.assert_array_equal(cupy.asnumpy(resp), cupy.asnumpy(msg))