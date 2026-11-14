import { Pipe, PipeTransform } from '@angular/core';

@Pipe({ name: 'markdown', standalone: true })
export class MarkdownPipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    return renderMarkdown(value ?? '');
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function inline(text: string): string {
  const codes: string[] = [];
  let out = text.replace(/`([^`]+)`/g, (_match, code: string) => {
    codes.push(`<code>${code}</code>`);
    return `\u0000${codes.length - 1}\u0000`;
  });
  out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  out = out.replace(
    /\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  );
  return out.replace(/\u0000(\d+)\u0000/g, (_match, index: string) => codes[Number(index)]);
}

function splitRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim());
}

function renderMarkdown(markdown: string): string {
  const lines = escapeHtml(markdown.replace(/\r\n/g, '\n')).split('\n');
  const out: string[] = [];
  let paragraph: string[] = [];
  let index = 0;

  const flush = () => {
    if (paragraph.length) {
      out.push(`<p>${inline(paragraph.join('<br>'))}</p>`);
      paragraph = [];
    }
  };

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      flush();
      index += 1;
      continue;
    }

    if (line.startsWith('```')) {
      flush();
      const code: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith('```')) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1;
      out.push(`<pre><code>${code.join('\n')}</code></pre>`);
      continue;
    }

    const isTableRow = /^\s*\|.*\|\s*$/.test(line);
    const isSeparator = index + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[index + 1]);
    if (isTableRow && isSeparator) {
      flush();
      const header = splitRow(line);
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && /^\s*\|.*\|\s*$/.test(lines[index])) {
        rows.push(splitRow(lines[index]));
        index += 1;
      }
      const head = header.map((cell) => `<th>${inline(cell)}</th>`).join('');
      const body = rows
        .map((row) => `<tr>${row.map((cell) => `<td>${inline(cell)}</td>`).join('')}</tr>`)
        .join('');
      out.push(
        `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`,
      );
      continue;
    }

    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      flush();
      const level = heading[1].length;
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      index += 1;
      continue;
    }

    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
      flush();
      out.push('<hr>');
      index += 1;
      continue;
    }

    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    if (bullet) {
      flush();
      const items = [bullet[1]];
      index += 1;
      while (index < lines.length) {
        const match = /^\s*[-*]\s+(.*)$/.exec(lines[index]);
        if (!match) {
          break;
        }
        items.push(match[1]);
        index += 1;
      }
      out.push(`<ul>${items.map((item) => `<li>${inline(item)}</li>`).join('')}</ul>`);
      continue;
    }

    const ordered = /^\s*\d+\.\s+(.*)$/.exec(line);
    if (ordered) {
      flush();
      const items = [ordered[1]];
      index += 1;
      while (index < lines.length) {
        const match = /^\s*\d+\.\s+(.*)$/.exec(lines[index]);
        if (!match) {
          break;
        }
        items.push(match[1]);
        index += 1;
      }
      out.push(`<ol>${items.map((item) => `<li>${inline(item)}</li>`).join('')}</ol>`);
      continue;
    }

    paragraph.push(line);
    index += 1;
  }

  flush();
  return out.join('');
}
