import type { ReactNode } from "react";

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    return <span key={index}>{part}</span>;
  });
}

export function RichText({ content }: { content: string }) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];

  function flushParagraph() {
    if (!paragraph.length) {
      return;
    }
    const text = paragraph.join(" ").trim();
    if (text) {
      blocks.push(<p key={`p-${blocks.length}`}>{renderInline(text)}</p>);
    }
    paragraph = [];
  }

  function flushList() {
    if (!listItems.length) {
      return;
    }
    blocks.push(
      <ul key={`ul-${blocks.length}`}>
        {listItems.map((item, index) => (
          <li key={index}>{renderInline(item)}</li>
        ))}
      </ul>,
    );
    listItems = [];
  }

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = /^(#{1,3})\s+(.*)$/.exec(trimmed);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = headingMatch[1].length;
      const headingText = headingMatch[2];
      if (level === 1) {
        blocks.push(<h2 key={`h2-${blocks.length}`}>{renderInline(headingText)}</h2>);
      } else if (level === 2) {
        blocks.push(<h3 key={`h3-${blocks.length}`}>{renderInline(headingText)}</h3>);
      } else {
        blocks.push(<h4 key={`h4-${blocks.length}`}>{renderInline(headingText)}</h4>);
      }
      continue;
    }

    if (/^---+$/.test(trimmed)) {
      flushParagraph();
      flushList();
      blocks.push(<hr key={`hr-${blocks.length}`} />);
      continue;
    }

    const bulletMatch = /^[-*]\s+(.*)$/.exec(trimmed);
    if (bulletMatch) {
      flushParagraph();
      listItems.push(bulletMatch[1]);
      continue;
    }

    flushList();
    paragraph.push(trimmed);
  }

  flushParagraph();
  flushList();

  return <div className="rich-text">{blocks}</div>;
}
