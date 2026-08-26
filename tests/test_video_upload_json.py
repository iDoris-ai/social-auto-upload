import asyncio
import io
import json
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, patch

import sau_cli


class VideoIdExtractionTests(unittest.TestCase):
    def test_video_id_from_url_bilibili(self):
        self.assertEqual(
            sau_cli._video_id_from_url("bilibili", "https://www.bilibili.com/video/BV1xx411c7mD/"),
            "BV1xx411c7mD",
        )

    def test_video_id_from_url_youtube_watch(self):
        self.assertEqual(
            sau_cli._video_id_from_url("youtube", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_video_id_from_url_youtube_short(self):
        self.assertEqual(
            sau_cli._video_id_from_url("youtube", "https://youtu.be/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_video_id_from_url_empty_input(self):
        self.assertEqual(sau_cli._video_id_from_url("bilibili", ""), "")

    def test_video_id_from_url_unrecognised_shape(self):
        self.assertEqual(sau_cli._video_id_from_url("bilibili", "https://example.com/not-a-video"), "")


class ExtractBvidUrlTests(unittest.TestCase):
    def test_finds_bvid_in_stdout(self):
        stdout = "上传中...\n投稿成功: https://www.bilibili.com/video/BV1xx411c7mD/\n"
        self.assertEqual(
            sau_cli._extract_bvid_url(stdout, ""),
            "https://www.bilibili.com/video/BV1xx411c7mD/",
        )

    def test_finds_bvid_in_stderr_when_stdout_has_none(self):
        self.assertEqual(
            sau_cli._extract_bvid_url("", "BV1yy411c7mE"),
            "https://www.bilibili.com/video/BV1yy411c7mE/",
        )

    def test_returns_empty_when_no_bvid_present(self):
        # This is the realistic case until someone confirms what biliup 1.2.4
        # actually prints on success — see the docstring on upload_bilibili_video.
        self.assertEqual(sau_cli._extract_bvid_url("投稿成功\n", "done"), "")


class PrintVideoUploadResultTests(unittest.TestCase):
    def test_json_mode_prints_full_shape(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            sau_cli.print_video_upload_result(
                "youtube", "creator", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", as_json=True
            )
        payload = json.loads(buf.getvalue())
        self.assertEqual(
            payload,
            {
                "platform": "youtube",
                "account": "creator",
                "id": "dQw4w9WgXcQ",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            },
        )

    def test_json_mode_with_unknown_url_reports_empty_fields_not_an_error(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            sau_cli.print_video_upload_result("bilibili", "creator", "", as_json=True)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload, {"platform": "bilibili", "account": "creator", "id": "", "url": ""})

    def test_text_mode_with_known_url(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            sau_cli.print_video_upload_result("bilibili", "creator", "https://www.bilibili.com/video/BV1xx/", as_json=False)
        self.assertIn("https://www.bilibili.com/video/BV1xx/", buf.getvalue())

    def test_text_mode_with_unknown_url_says_check_manually(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            sau_cli.print_video_upload_result("youtube", "creator", "", as_json=False)
        self.assertIn("could not be read back", buf.getvalue())


class UploadVideoJsonFlagParserTests(unittest.TestCase):
    def setUp(self):
        # --file uses type=existing_file_path, which stats the path — needs a real file.
        self._tmp = tempfile.NamedTemporaryFile(suffix=".mp4")
        self.addCleanup(self._tmp.close)
        self.video_path = self._tmp.name

    def test_bilibili_upload_video_accepts_json_flag(self):
        parser = sau_cli.build_parser()
        args = parser.parse_args(
            [
                "bilibili",
                "upload-video",
                "--account",
                "creator",
                "--file",
                self.video_path,
                "--title",
                "hello",
                "--desc",
                "hello",
                "--tid",
                "188",
                "--json",
            ]
        )
        self.assertTrue(args.json)

    def test_bilibili_upload_video_json_defaults_false(self):
        parser = sau_cli.build_parser()
        args = parser.parse_args(
            [
                "bilibili",
                "upload-video",
                "--account",
                "creator",
                "--file",
                self.video_path,
                "--title",
                "hello",
                "--desc",
                "hello",
                "--tid",
                "188",
            ]
        )
        self.assertFalse(args.json)

    def test_youtube_upload_video_accepts_json_flag(self):
        parser = sau_cli.build_parser()
        args = parser.parse_args(
            [
                "youtube",
                "upload-video",
                "--account",
                "creator",
                "--file",
                self.video_path,
                "--title",
                "hello",
                "--json",
            ]
        )
        self.assertTrue(args.json)


class DispatchUploadVideoJsonTests(unittest.TestCase):
    def test_dispatch_bilibili_upload_video_json_uses_returned_url(self):
        args = Namespace(
            platform="bilibili",
            action="upload-video",
            account="creator",
            file="demo.mp4",
            title="hello",
            desc="hello",
            tid=188,
            tags="",
            schedule=None,
            thumbnail=None,
            json=True,
        )
        buf = io.StringIO()
        with patch(
            "sau_cli.upload_bilibili_video",
            new=AsyncMock(return_value="https://www.bilibili.com/video/BV1xx411c7mD/"),
        ):
            with redirect_stdout(buf):
                code = asyncio.run(sau_cli.dispatch(args))
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["url"], "https://www.bilibili.com/video/BV1xx411c7mD/")
        self.assertEqual(payload["id"], "BV1xx411c7mD")

    def test_dispatch_youtube_upload_video_json_uses_returned_url(self):
        args = Namespace(
            platform="youtube",
            action="upload-video",
            account="creator",
            file="demo.mp4",
            title="hello",
            desc="",
            tags="",
            thumbnail=None,
            playlist=None,
            visibility="private",
            debug=False,
            headless=False,
            json=True,
        )
        buf = io.StringIO()
        with patch(
            "sau_cli.upload_youtube_video",
            new=AsyncMock(return_value="https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ):
            with redirect_stdout(buf):
                code = asyncio.run(sau_cli.dispatch(args))
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["url"], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(payload["id"], "dQw4w9WgXcQ")

    def test_dispatch_bilibili_upload_video_json_with_unresolved_url(self):
        # sau couldn't scrape a bvid out of biliup's output — must not fabricate one.
        args = Namespace(
            platform="bilibili",
            action="upload-video",
            account="creator",
            file="demo.mp4",
            title="hello",
            desc="hello",
            tid=188,
            tags="",
            schedule=None,
            thumbnail=None,
            json=True,
        )
        buf = io.StringIO()
        with patch("sau_cli.upload_bilibili_video", new=AsyncMock(return_value="")):
            with redirect_stdout(buf):
                code = asyncio.run(sau_cli.dispatch(args))
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload, {"platform": "bilibili", "account": "creator", "id": "", "url": ""})


if __name__ == "__main__":
    unittest.main()
