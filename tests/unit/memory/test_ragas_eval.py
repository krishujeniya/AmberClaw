# ruff: noqa: E402, PLR2004
"""Unit tests for the RAGAS RAG evaluation script."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add scripts directory to path to import eval_rag
scripts_dir = Path(__file__).parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

import eval_rag


@pytest.mark.asyncio
async def test_generate_rag_dataset():
    # Mock Retriever
    mock_retriever = MagicMock()
    mock_retriever_obj = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "This is a test context about AmberClaw."
    mock_retriever_obj.invoke.return_value = [mock_doc]
    mock_retriever.get_retriever.return_value = mock_retriever_obj

    # Mock Provider
    mock_provider = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "AmberClaw has memory layers."
    mock_provider.chat_with_retry = AsyncMock(return_value=mock_response)

    eval_data = [
        {
            "question": "What is AmberClaw?",
            "ground_truth": "AmberClaw is an AI OS kernel.",
            "contexts_fallback": ["Fallback context"]
        }
    ]

    # Test with live=True
    data_dict = await eval_rag.generate_rag_dataset(
        mock_retriever, mock_provider, eval_data, live=True
    )

    assert data_dict["question"] == ["What is AmberClaw?"]
    assert data_dict["contexts"] == [["This is a test context about AmberClaw."]]
    assert data_dict["answer"] == ["AmberClaw has memory layers."]
    assert data_dict["ground_truth"] == ["AmberClaw is an AI OS kernel."]

    # Test with live=False
    data_dict_fallback = await eval_rag.generate_rag_dataset(
        mock_retriever, mock_provider, eval_data, live=False
    )
    assert data_dict_fallback["contexts"] == [["Fallback context"]]
    assert data_dict_fallback["answer"] == ["Mock answer matching ground truth: AmberClaw is an AI OS kernel."]


def test_run_ragas_evaluation_mock():
    data_dict = {
        "question": ["What is AmberClaw?"],
        "contexts": [["This is a test context about AmberClaw."]],
        "answer": ["AmberClaw has memory layers."],
        "ground_truth": ["AmberClaw is an AI OS kernel."]
    }

    results = eval_rag.run_ragas_evaluation(data_dict, mock_eval=True)
    assert "faithfulness" in results
    assert "answer_relevancy" in results
    assert "context_precision" in results
    assert results["faithfulness"] == 0.88


def test_main_execution(tmp_path):
    output_file = tmp_path / "report.json"
    
    # Test script main with args
    test_args = [
        "eval_rag.py",
        "--workspace", str(tmp_path),
        "--mock-eval",
        "--output", str(output_file)
    ]
    
    with patch("eval_rag.HybridRetriever"), \
         patch("eval_rag.make_provider"), \
         patch("eval_rag.load_config"), \
         patch("eval_rag.generate_rag_dataset") as mock_gen_dataset, \
         patch("eval_rag.run_ragas_evaluation") as mock_run_eval, \
         patch("sys.argv", test_args):
         
        mock_run_eval.return_value = {
            "faithfulness": 0.9,
            "answer_relevancy": 0.85,
            "context_precision": 0.8
        }
        mock_gen_dataset.return_value = {
            "question": ["q"], "contexts": [["c"]], "answer": ["a"], "ground_truth": ["g"]
        }
        
        eval_rag.main()

    assert output_file.exists()
