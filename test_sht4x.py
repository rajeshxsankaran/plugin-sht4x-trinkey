import pytest

from sht4x import ParseError, Sample, parse_banner_serial, parse_line


def test_parses_data_line():
    sample = parse_line("359993150, 21.14, 12.77, 178")
    assert sample == Sample(serial_number=359993150, temperature=21.14, humidity=12.77, touch=178)
    assert sample.serial_hex == "0x15750F3E"


def test_ignores_comments_and_blanks():
    assert parse_line("# Adafruit SHT4x Trinkey Factory Test") is None
    assert parse_line("") is None
    assert parse_line("   \r\n") is None


def test_banner_serial_matches_data_line_serial():
    banner = parse_banner_serial("# Found SHT4x sensor. Serial number 0x15750F3E")
    sample = parse_line("359993150, 21.14, 12.77, 178")
    assert banner == sample.serial_number


def test_banner_serial_absent():
    assert parse_banner_serial("# Serial number, Temperature in *C, Relative Humidity %, Touch") is None


@pytest.mark.parametrize(
    "line",
    [
        "359993150, 21.14, 12.77",  # truncated
        "359993150, nan-ish, 12.77, 178",  # unparseable field
        "359993150, 999.0, 12.77, 178",  # temperature out of range
        "359993150, 21.14, 250.0, 178",  # humidity out of range
        "359993150, 21.14, 12.77, 99999",  # touch out of range
    ],
)
def test_rejects_bad_lines(line):
    with pytest.raises(ParseError):
        parse_line(line)


def test_partial_first_line_is_rejected_not_misread():
    # A USB re-enumeration often leaves a fragment in the buffer.
    with pytest.raises(ParseError):
        parse_line("50, 21.14, 12.7")


def test_aggregator_mean_over_sample_stream():
    from main import Aggregator

    aggregator = Aggregator()
    with open("test/sample_stream.txt") as f:
        for line in f:
            sample = parse_line(line)
            if sample is not None:
                aggregator.add(sample)

    assert len(aggregator) == 17
    summary = aggregator.summarize("mean")
    assert summary["count"] == 17
    assert summary["temperature"] == pytest.approx(21.131, abs=0.01)
    assert summary["relative_humidity"] == pytest.approx(12.752, abs=0.01)
    assert summary["temperature_min"] == 21.10
    assert summary["temperature_max"] == 21.17


def test_aggregator_last_takes_final_sample():
    from main import Aggregator

    aggregator = Aggregator()
    aggregator.add(Sample(1, 20.0, 50.0, 100))
    aggregator.add(Sample(1, 22.0, 52.0, 102))
    summary = aggregator.summarize("last")
    assert summary["temperature"] == 22.0
    assert summary["relative_humidity"] == 52.0
