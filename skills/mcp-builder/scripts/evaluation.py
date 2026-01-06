#!/usr/bin/env python3
"""MCP Server Evaluation Harness.

Evaluates MCP servers by running test questions and measuring accuracy.
"""

import argparse
import asyncio
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import anthropic

from connections import create_connection, MCPConnection


@dataclass
class QAPair:
    question: str
    expected_answer: str


@dataclass
class EvaluationResult:
    question: str
    expected: str
    actual: str
    correct: bool
    duration: float
    tool_calls: int
    summary: str
    feedback: str


@dataclass
class EvaluationMetrics:
    total: int = 0
    correct: int = 0
    total_duration: float = 0.0
    total_tool_calls: int = 0
    results: List[EvaluationResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0

    @property
    def avg_duration(self) -> float:
        return self.total_duration / self.total if self.total > 0 else 0.0

    @property
    def avg_tool_calls(self) -> float:
        return self.total_tool_calls / self.total if self.total > 0 else 0.0


def parse_evaluation_file(path: str) -> List[QAPair]:
    """Parse XML evaluation file into QA pairs."""
    tree = ET.parse(path)
    root = tree.getroot()
    pairs = []
    for qa in root.findall("qa_pair"):
        question = qa.find("question").text.strip()
        answer = qa.find("answer").text.strip()
        pairs.append(QAPair(question, answer))
    return pairs


def extract_xml_section(text: str, tag: str) -> str:
    """Extract content from XML-style tags."""
    pattern = f"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


async def agent_loop(
    client: anthropic.AsyncAnthropic,
    connection: MCPConnection,
    question: str,
    model: str = "claude-sonnet-4-20250514"
) -> Tuple[str, int, str, str]:
    """Run agent loop to answer question using MCP tools."""
    tools = await connection.list_tools()
    tool_calls = 0

    # convert mcp tools to anthropic format
    anthropic_tools = [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["input_schema"]
        }
        for tool in tools
    ]

    messages = [
        {
            "role": "user",
            "content": f"""Answer this question using the available tools:

{question}

After finding the answer, respond with:
<summary>Brief description of how you found the answer</summary>
<feedback>Any suggestions for improving the tools</feedback>
<response>The final answer</response>"""
        }
    ]

    while True:
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            tools=anthropic_tools,
            messages=messages
        )

        # check for tool use
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            # no more tool calls, extract response
            text_content = "".join(
                b.text for b in response.content if b.type == "text"
            )
            summary = extract_xml_section(text_content, "summary")
            feedback = extract_xml_section(text_content, "feedback")
            answer = extract_xml_section(text_content, "response")
            return answer, tool_calls, summary, feedback

        # execute tool calls
        tool_results = []
        for tool_use in tool_use_blocks:
            tool_calls += 1
            result = await connection.call_tool(tool_use.name, tool_use.input)
            result_text = json.dumps(result) if not isinstance(result, str) else result
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result_text
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})


async def evaluate_single_task(
    client: anthropic.AsyncAnthropic,
    connection: MCPConnection,
    qa: QAPair,
    model: str
) -> EvaluationResult:
    """Evaluate a single QA pair."""
    start = time.time()
    answer, tool_calls, summary, feedback = await agent_loop(
        client, connection, qa.question, model
    )
    duration = time.time() - start

    # simple string comparison (could be more sophisticated)
    correct = answer.strip().lower() == qa.expected_answer.strip().lower()

    return EvaluationResult(
        question=qa.question,
        expected=qa.expected_answer,
        actual=answer,
        correct=correct,
        duration=duration,
        tool_calls=tool_calls,
        summary=summary,
        feedback=feedback
    )


async def run_evaluation(
    connection: MCPConnection,
    qa_pairs: List[QAPair],
    model: str
) -> EvaluationMetrics:
    """Run full evaluation suite."""
    client = anthropic.AsyncAnthropic()
    metrics = EvaluationMetrics()

    async with connection:
        for qa in qa_pairs:
            result = await evaluate_single_task(client, connection, qa, model)
            metrics.total += 1
            metrics.correct += 1 if result.correct else 0
            metrics.total_duration += result.duration
            metrics.total_tool_calls += result.tool_calls
            metrics.results.append(result)

    return metrics


def generate_report(metrics: EvaluationMetrics) -> str:
    """Generate markdown evaluation report."""
    lines = [
        "# MCP Server Evaluation Report",
        "",
        "## Summary",
        "",
        f"- **Accuracy**: {metrics.accuracy:.1%} ({metrics.correct}/{metrics.total})",
        f"- **Avg Duration**: {metrics.avg_duration:.2f}s",
        f"- **Avg Tool Calls**: {metrics.avg_tool_calls:.1f}",
        "",
        "## Results",
        ""
    ]

    for i, result in enumerate(metrics.results, 1):
        status = "PASS" if result.correct else "FAIL"
        lines.extend([
            f"### Task {i}: {status}",
            "",
            f"**Question**: {result.question}",
            "",
            f"**Expected**: {result.expected}",
            "",
            f"**Actual**: {result.actual}",
            "",
            f"**Duration**: {result.duration:.2f}s | **Tool Calls**: {result.tool_calls}",
            "",
            f"**Summary**: {result.summary}",
            "",
            f"**Feedback**: {result.feedback}",
            "",
            "---",
            ""
        ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Evaluate MCP server")
    parser.add_argument("--transport", choices=["stdio", "sse", "http"], required=True)
    parser.add_argument("--command", help="Command for stdio transport")
    parser.add_argument("--url", help="URL for sse/http transport")
    parser.add_argument("--evaluation", required=True, help="Path to evaluation XML")
    parser.add_argument("--output", default="results.md", help="Output file")
    parser.add_argument("--model", default="claude-sonnet-4-20250514")
    args = parser.parse_args()

    connection = create_connection(
        transport=args.transport,
        command=args.command,
        url=args.url
    )

    qa_pairs = parse_evaluation_file(args.evaluation)

    metrics = asyncio.run(run_evaluation(connection, qa_pairs, args.model))

    report = generate_report(metrics)
    with open(args.output, "w") as f:
        f.write(report)

    print(f"Evaluation complete: {metrics.accuracy:.1%} accuracy")
    print(f"Report saved to {args.output}")


if __name__ == "__main__":
    main()
