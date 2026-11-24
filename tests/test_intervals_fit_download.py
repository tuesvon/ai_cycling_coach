
from unittest.mock import patch, Mock

from src.integrations.intervals_api import (
    download_activity_fit,
)


def test_intervals_fit_download():
    fake_fit_content = b"FAKE_FIT_CONTENT"

    response = Mock()
    response.content = fake_fit_content
    response.raise_for_status.return_value = None

    with patch(
        "src.integrations.intervals_api.requests.get",
        return_value=response,
    ) as mocked_get:

        result = download_activity_fit(
            activity_id="i123456",
            api_key="test_api_key",
        )

    assert result == fake_fit_content

    mocked_get.assert_called_once()

    args, kwargs = mocked_get.call_args

    assert args[0].endswith(
        "/activity/i123456/file"
    )

    assert kwargs["auth"] == (
        "API_KEY",
        "test_api_key",
    )

    print("FIT DOWNLOAD REQUEST TEST PASSED")

    empty_response = Mock()
    empty_response.content = b""
    empty_response.raise_for_status.return_value = None

    with patch(
        "src.integrations.intervals_api.requests.get",
        return_value=empty_response,
    ):
        try:
            download_activity_fit(
                "i123456",
                api_key="test_api_key",
            )
        except ValueError:
            print("EMPTY FIT RESPONSE TEST PASSED")
        else:
            raise AssertionError(
                "Пустой ответ должен вызывать ValueError"
            )

    print("Все тесты загрузки FIT пройдены!")


if __name__ == "__main__":
    test_intervals_fit_download()
