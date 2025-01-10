# type: ignore
import pytest
from unittest import mock

from access_py_telemetry.cli import configure_telemetry


@pytest.fixture
def test_dir(tmp_path):
    return tmp_path


@pytest.mark.parametrize(
    "argv, expected_output, expected_ret_code",
    [
        (["--disable"], "Telemetry already disabled.\n", 0),
        (["--enable"], "Telemetry enabled.\n", 0),
        (["--status"], "Telemetry disabled.\n", 0),
        (
            ["--disable", "--enable"],
            "Only one of --disable, --enable, or --status can be used at a time.\n",
            1,
        ),
    ],
)
@mock.patch("pathlib.Path.home")
def test_configure_telemetry(
    home, test_dir, capsys, argv, expected_output, expected_ret_code
):
    home.return_value = test_dir

    ret_code = configure_telemetry(argv)
    output = capsys.readouterr()

    assert output.out == expected_output
    assert ret_code == expected_ret_code


@mock.patch("pathlib.Path.home")
def test_telemetry_configure_helpmsg(home, test_dir, capsys):
    home.return_value = test_dir

    ret_code = configure_telemetry([])
    output = capsys.readouterr()

    assert (
        "[-h] [--disable] [--enable] [--status] [--silent]\n\nConfigure ipython telemetry.\n\noptions:\n  -h, --help  show this help message and exit\n  --disable   Disable telemetry.\n  --enable    Enable telemetry.\n  --status    Check telemetry status.\n  --silent    Suppress output.\n"
        in output.out
    )

    assert ret_code == 0


@pytest.mark.parametrize(
    "argv1, argv2, expected_output_1, expected_output_2,",
    [
        (
            ["--enable"],
            ["--status"],
            "Telemetry enabled.\n",
            "Telemetry enabled.\n",
        ),
        (
            ["--enable"],
            ["--disable"],
            "Telemetry enabled.\n",
            "Telemetry disabled.\n",
        ),
        (
            ["--disable"],
            ["--status"],
            "Telemetry already disabled.\n",
            "Telemetry disabled.\n",
        ),
        (
            ["--enable"],
            ["--enable"],
            "Telemetry enabled.\n",
            "Telemetry already enabled.\n",
        ),
    ],
)
@mock.patch("pathlib.Path.home")
def test_telemetry_runtwice(
    home, test_dir, capsys, argv1, argv2, expected_output_1, expected_output_2
):
    home.return_value = test_dir

    configure_telemetry(argv1)
    output_1 = capsys.readouterr()

    configure_telemetry(argv2)
    output_2 = capsys.readouterr()

    assert output_1.out == expected_output_1
    assert output_2.out == expected_output_2


@mock.patch("pathlib.Path.home")
def test_telemetry_corrupted(home, test_dir, capsys):
    """
    After enabling telemetry, we will corrupt the telemetry file and check if the status is reported correctly.
    """
    home.return_value = test_dir

    configure_telemetry(["--enable"])
    output_1 = capsys.readouterr()

    telemetry_fname = (
        test_dir / ".ipython" / "profile_default" / "startup" / "telemetry.py"
    )

    with open(telemetry_fname, "w") as f:
        f.write("Corrupted file")

    configure_telemetry(["--status"])
    output_2 = capsys.readouterr()

    assert output_1.out == "Telemetry enabled.\n"
    assert (
        output_2.out
        == "Telemetry enabled but misconfigured. Run `access-py-telemetry --disable && access-py-telemetry --enable` to fix.\n"
    )
