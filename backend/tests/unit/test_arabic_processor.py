"""
Unit tests for ArabicAwareTextSplitter — chunking strategy correctness.
Run: pytest backend/tests/unit/test_arabic_processor.py -v
"""
import pytest


class TestArabicAwareTextSplitter:
    """Tests for chunk splitting with Arabic sentence boundary awareness."""

    def setup_method(self) -> None:
        from app.rag.indexer import ArabicAwareTextSplitter

        self.splitter = ArabicAwareTextSplitter(chunk_size=50, overlap=5)

    def test_split_returns_list_of_dicts(self) -> None:
        chunks = self.splitter.split("نص تجريبي بسيط. جملة ثانية للاختبار.")
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        for chunk in chunks:
            assert "text" in chunk
            assert "token_count" in chunk

    def test_split_non_empty_text(self) -> None:
        text = "يحق للموظف الحصول على 21 يوم عمل كإجازة سنوية مدفوعة الأجر. تُحتسب الإجازة بدءاً من تاريخ التعيين."
        chunks = self.splitter.split(text)
        assert len(chunks) >= 1
        # All chunk texts should be non-empty
        assert all(len(c["text"].strip()) > 0 for c in chunks)

    def test_empty_text_returns_empty_list(self) -> None:
        assert self.splitter.split("") == []
        assert self.splitter.split("   ") == []

    def test_chunks_cover_source_content(self) -> None:
        text = "الجملة الأولى تحتوي على معلومات مهمة. الجملة الثانية مكملة. الجملة الثالثة للختام."
        chunks = self.splitter.split(text)
        combined = " ".join(c["text"] for c in chunks)
        # Key words should appear in combined chunks
        assert "الأولى" in combined
        assert "الثانية" in combined

    def test_chunk_size_respected(self) -> None:
        # With chunk_size=50 words, large texts should produce multiple chunks
        words = ["كلمة"] * 200
        text = " ".join(words)
        chunks = self.splitter.split(text)
        # Should produce multiple chunks
        assert len(chunks) > 1

    def test_overlap_creates_shared_content(self) -> None:
        from app.rag.indexer import ArabicAwareTextSplitter
        splitter = ArabicAwareTextSplitter(chunk_size=10, overlap=3)
        text = " ".join([f"كلمة{i}" for i in range(50)])
        chunks = splitter.split(text)
        if len(chunks) >= 2:
            # The last few words of chunk[0] should appear in chunk[1]'s beginning
            chunk0_words = chunks[0]["text"].split()[-3:]
            chunk1_text = chunks[1]["text"]
            # At least some overlap words should appear
            overlap_found = any(w in chunk1_text for w in chunk0_words)
            assert overlap_found, "Overlap tokens should appear in next chunk"

    def test_handles_english_text(self) -> None:
        text = "Annual leave policy states employees get 21 days per year. Remote work is allowed two days per week."
        chunks = self.splitter.split(text)
        assert len(chunks) >= 1
        assert all(len(c["text"]) > 0 for c in chunks)

    def test_handles_mixed_arabic_english(self) -> None:
        text = "سياسة الإجازة السنوية: Annual leave is 21 days. تُحتسب من تاريخ التعيين."
        chunks = self.splitter.split(text)
        assert len(chunks) >= 1

    def test_token_count_in_metadata(self) -> None:
        text = "جملة قصيرة. جملة أخرى."
        chunks = self.splitter.split(text)
        for chunk in chunks:
            assert isinstance(chunk["token_count"], int)
            assert chunk["token_count"] > 0


class TestHandbookIngestionPipeline:
    """Tests for the ingestion pipeline setup (no external services)."""

    def test_splitter_instantiates_with_default_settings(self) -> None:
        from app.rag.indexer import ArabicAwareTextSplitter
        from app.core.config import settings

        splitter = ArabicAwareTextSplitter(
            chunk_size=settings.RAG_CHUNK_SIZE,
            overlap=settings.RAG_CHUNK_OVERLAP,
        )
        assert splitter.chunk_size == settings.RAG_CHUNK_SIZE
        assert splitter.overlap == settings.RAG_CHUNK_OVERLAP

    def test_supported_extensions_includes_docx(self) -> None:
        from app.rag.indexer import SUPPORTED_EXTENSIONS

        assert ".docx" in SUPPORTED_EXTENSIONS
        assert ".pdf"  in SUPPORTED_EXTENSIONS
        assert ".md"   in SUPPORTED_EXTENSIONS

    def test_pipeline_docx_extraction_imports_correctly(self) -> None:
        """Ensure python-docx is importable (installed in environment)."""
        import docx  # noqa: F401
