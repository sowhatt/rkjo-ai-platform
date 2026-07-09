from rkjo_kernel.kernel import RKJOKernel


def test_kernel_start_stop():
    kernel = RKJOKernel()

    assert kernel.health()["status"] == "stopped"

    kernel.start()
    assert kernel.health()["status"] == "started"

    kernel.stop()
    assert kernel.health()["status"] == "stopped"