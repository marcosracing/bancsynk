from bancsynk.gateway import BancSynk


def test_gateway_registers_btg_adapter_without_credentials():
    gateway = BancSynk()

    adapter = gateway.get_adapter("btg")

    assert adapter.banco_codigo == "btg"
    assert adapter.read_only is True


def test_write_operations_are_blocked_in_phase_1():
    adapter = BancSynk().get_adapter("btg")

    try:
        adapter.send_pix({})
    except NotImplementedError as exc:
        assert "Fase 1 read-only" in str(exc)
    else:
        raise AssertionError("send_pix deveria estar bloqueado na Fase 1")
