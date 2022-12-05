from pathlib import Path

from test_base import TestOT2_Base


class Test_Protopiler_Base(TestOT2_Base):
    def test_payload_injection(self):
        import ot2_driver
        from ot2_driver.protopiler.protopiler import ProtoPiler

        cfg = (
            Path(ot2_driver.__file__).parent.resolve()
            / "protopiler"
            / "test_configs"
            / "test_payload_config.yaml"
        )

        payload = {"destinations": "2:A10"}

        protopiler = ProtoPiler(cfg)
        temp_out_py = Path() / "test_out.py"
        temp_out_resource = Path() / "resources.json"
        protopiler.yaml_to_protocol(
            cfg,
            payload=payload,
            protocol_out=temp_out_py,
            resource_file_out=temp_out_resource,
        )

        assert cfg.exists()
        assert temp_out_py.exists()
        assert temp_out_resource.exists()
