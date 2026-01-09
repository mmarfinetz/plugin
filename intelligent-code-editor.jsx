/**
 * Intelligent Code Editor - AI-Powered Coding Assistant
 *
 * A production-quality browser-based code editor with:
 * - Smart context-aware code completion
 * - Real-time error detection and highlighting
 * - Contextual intelligence panel
 * - Multi-language support (JS/TS, Python, Rust, SQL, JSON/YAML)
 *
 * Usage:
 * - Just start typing! Suggestions appear automatically after 300ms pause
 * - Tab: Accept suggestion | Escape: Dismiss | ↑/↓: Cycle suggestions
 * - Ctrl+Space: Manual trigger | Ctrl+I: Toggle intelligence panel
 * - F8: Next error | Ctrl+.: Quick fix
 *
 * @requires React 18+
 * @requires Anthropic API key passed as prop
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';

// ============================================================================
// CONSTANTS & CONFIGURATION
// ============================================================================

const LANGUAGES = {
  javascript: { name: 'JavaScript', extensions: ['.js', '.jsx'], icon: 'JS' },
  typescript: { name: 'TypeScript', extensions: ['.ts', '.tsx'], icon: 'TS' },
  python: { name: 'Python', extensions: ['.py'], icon: 'PY' },
  rust: { name: 'Rust', extensions: ['.rs'], icon: 'RS' },
  sql: { name: 'SQL', extensions: ['.sql'], icon: 'SQL' },
  json: { name: 'JSON', extensions: ['.json'], icon: '{}' },
  yaml: { name: 'YAML', extensions: ['.yaml', '.yml'], icon: 'YML' },
};

const SEVERITY_COLORS = {
  error: { bg: 'rgba(243, 139, 168, 0.2)', border: '#f38ba8', text: '#f38ba8' },
  warning: { bg: 'rgba(250, 179, 135, 0.2)', border: '#fab387', text: '#fab387' },
  info: { bg: 'rgba(137, 220, 235, 0.2)', border: '#89dceb', text: '#89dceb' },
};

const DEBOUNCE_COMPLETION = 300;
const DEBOUNCE_ANALYSIS = 500;

// Sample code for initial state
const SAMPLE_CODE = `// Welcome to the Intelligent Code Editor!
// Start typing to see AI-powered suggestions

function calculateTotal(items) {
  // Try typing here - suggestions will appear
  return items.reduce((sum, item) => {
    return sum + item.price * item.quantity;
  }, 0);
}

// Example with intentional issues for error detection
const unusedVariable = "I'm never used";

async function fetchUserData(userId) {
  const response = await fetch(\`/api/users/\${userId}\`);
  const data = response.json(); // Missing await
  return data;
}

// Try completing this function:
function greet(name) {

}
`;

// ============================================================================
// SYNTAX HIGHLIGHTING PATTERNS
// ============================================================================

const SYNTAX_PATTERNS = {
  javascript: {
    keywords: /\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|async|await|class|extends|new|this|super|import|export|default|from|typeof|instanceof|in|of|true|false|null|undefined|void)\b/g,
    strings: /(["'`])(?:(?!\1|\\).|\\.)*?\1/g,
    comments: /(\/\/.*$|\/\*[\s\S]*?\*\/)/gm,
    numbers: /\b(\d+\.?\d*|0x[0-9a-fA-F]+)\b/g,
    functions: /\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?=\()/g,
    operators: /([+\-*/%=<>!&|^~?:]+)/g,
  },
  typescript: {
    keywords: /\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|async|await|class|extends|new|this|super|import|export|default|from|typeof|instanceof|in|of|true|false|null|undefined|void|interface|type|enum|namespace|module|declare|readonly|private|public|protected|static|abstract|implements|as|is|keyof|infer|never|unknown|any)\b/g,
    strings: /(["'`])(?:(?!\1|\\).|\\.)*?\1/g,
    comments: /(\/\/.*$|\/\*[\s\S]*?\*\/)/gm,
    numbers: /\b(\d+\.?\d*|0x[0-9a-fA-F]+)\b/g,
    functions: /\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?=\()/g,
    types: /\b([A-Z][a-zA-Z0-9]*)\b/g,
  },
  python: {
    keywords: /\b(def|class|return|if|elif|else|for|while|break|continue|try|except|finally|raise|with|as|import|from|pass|lambda|yield|global|nonlocal|assert|True|False|None|and|or|not|in|is|async|await)\b/g,
    strings: /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g,
    comments: /(#.*$)/gm,
    numbers: /\b(\d+\.?\d*|0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+)\b/g,
    functions: /\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()/g,
    decorators: /(@\w+)/g,
  },
  rust: {
    keywords: /\b(fn|let|mut|const|static|if|else|match|loop|while|for|in|break|continue|return|struct|enum|impl|trait|type|where|pub|mod|use|crate|self|super|as|ref|move|async|await|unsafe|extern|dyn|true|false|Some|None|Ok|Err)\b/g,
    strings: /(r#*"[\s\S]*?"#*|"(?:[^"\\]|\\.)*")/g,
    comments: /(\/\/.*$|\/\*[\s\S]*?\*\/)/gm,
    numbers: /\b(\d+\.?\d*|0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+)([ui](8|16|32|64|128|size)|f(32|64))?\b/g,
    functions: /\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()/g,
    macros: /\b([a-zA-Z_][a-zA-Z0-9_]*!)/g,
    lifetimes: /('\w+)/g,
  },
  sql: {
    keywords: /\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AND|OR|NOT|IN|LIKE|BETWEEN|IS|NULL|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|INDEX|VIEW|DROP|ALTER|ADD|COLUMN|PRIMARY|KEY|FOREIGN|REFERENCES|UNIQUE|DEFAULT|CONSTRAINT|CASCADE|DISTINCT|AS|UNION|ALL|EXISTS|CASE|WHEN|THEN|ELSE|END|COUNT|SUM|AVG|MIN|MAX)\b/gi,
    strings: /('(?:[^'\\]|\\.)*')/g,
    comments: /(--.*$|\/\*[\s\S]*?\*\/)/gm,
    numbers: /\b(\d+\.?\d*)\b/g,
  },
  json: {
    strings: /("(?:[^"\\]|\\.)*")\s*:/g,
    values: /:\s*("(?:[^"\\]|\\.)*")/g,
    numbers: /:\s*(-?\d+\.?\d*)/g,
    keywords: /\b(true|false|null)\b/g,
  },
  yaml: {
    keys: /^(\s*[\w-]+)\s*:/gm,
    strings: /(["'])(?:(?!\1|\\).|\\.)*?\1/g,
    comments: /(#.*$)/gm,
    numbers: /:\s*(-?\d+\.?\d*)\b/g,
    keywords: /\b(true|false|null|yes|no|on|off)\b/gi,
  },
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Debounce function that returns a promise
 */
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Detect language from code content
 */
function detectLanguage(code) {
  const patterns = {
    typescript: [/interface\s+\w+/, /type\s+\w+\s*=/, /:\s*(string|number|boolean|any)\b/, /<\w+>/],
    javascript: [/function\s+\w+/, /const\s+\w+\s*=/, /=>\s*{/, /require\(/, /module\.exports/],
    python: [/def\s+\w+\(/, /import\s+\w+/, /from\s+\w+\s+import/, /:\s*$/, /elif\s+/],
    rust: [/fn\s+\w+/, /let\s+mut/, /impl\s+/, /pub\s+fn/, /->/, /&mut/, /::/, /!"/],
    sql: [/SELECT\s+/i, /FROM\s+/i, /WHERE\s+/i, /INSERT\s+INTO/i, /CREATE\s+TABLE/i],
    json: [/^\s*{[\s\S]*}$/, /"[\w]+"\s*:/],
    yaml: [/^\s*[\w-]+\s*:\s*/, /^\s*-\s+/m],
  };

  let maxScore = 0;
  let detected = 'javascript';

  for (const [lang, langPatterns] of Object.entries(patterns)) {
    const score = langPatterns.reduce((acc, pattern) =>
      acc + (pattern.test(code) ? 1 : 0), 0);
    if (score > maxScore) {
      maxScore = score;
      detected = lang;
    }
  }

  return detected;
}

/**
 * Get cursor position info from textarea
 */
function getCursorInfo(textarea) {
  const { selectionStart, value } = textarea;
  const beforeCursor = value.substring(0, selectionStart);
  const afterCursor = value.substring(selectionStart);
  const lines = beforeCursor.split('\n');
  const line = lines.length;
  const column = lines[lines.length - 1].length + 1;

  return { line, column, beforeCursor, afterCursor, position: selectionStart };
}

/**
 * Apply syntax highlighting to code
 */
function highlightCode(code, language) {
  const patterns = SYNTAX_PATTERNS[language] || SYNTAX_PATTERNS.javascript;
  let highlighted = escapeHtml(code);

  // Order matters - comments first, then strings, then rest
  const replacements = [];

  // Collect all matches with their positions
  if (patterns.comments) {
    let match;
    const regex = new RegExp(patterns.comments.source, patterns.comments.flags);
    while ((match = regex.exec(code)) !== null) {
      replacements.push({
        start: match.index,
        end: match.index + match[0].length,
        type: 'comment',
        text: match[0]
      });
    }
  }

  if (patterns.strings) {
    let match;
    const regex = new RegExp(patterns.strings.source, patterns.strings.flags);
    while ((match = regex.exec(code)) !== null) {
      const overlap = replacements.some(r =>
        (match.index >= r.start && match.index < r.end) ||
        (match.index + match[0].length > r.start && match.index + match[0].length <= r.end)
      );
      if (!overlap) {
        replacements.push({
          start: match.index,
          end: match.index + match[0].length,
          type: 'string',
          text: match[0]
        });
      }
    }
  }

  // Sort by position descending to replace from end to start
  replacements.sort((a, b) => b.start - a.start);

  // Apply replacements
  for (const r of replacements) {
    const before = highlighted.substring(0, r.start);
    const after = highlighted.substring(r.end);
    const className = r.type === 'comment' ? 'syntax-comment' : 'syntax-string';
    highlighted = before + `<span class="${className}">${escapeHtml(r.text)}</span>` + after;
  }

  // Apply keyword highlighting (avoiding already highlighted sections)
  if (patterns.keywords) {
    highlighted = highlighted.replace(
      /(?<!<[^>]*)(\b(?:const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|try|catch|finally|throw|async|await|class|extends|new|this|super|import|export|default|from|typeof|instanceof|in|of|true|false|null|undefined|void|def|elif|match|loop|struct|enum|impl|trait|pub|mod|use|crate|mut|fn|interface|type)\b)(?![^<]*>)/g,
      '<span class="syntax-keyword">$1</span>'
    );
  }

  // Apply number highlighting
  highlighted = highlighted.replace(
    /(?<!<[^>]*)(\b\d+\.?\d*\b)(?![^<]*>)/g,
    '<span class="syntax-number">$1</span>'
  );

  // Apply function highlighting
  highlighted = highlighted.replace(
    /(?<!<[^>]*)(\b[a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?=\()/g,
    '<span class="syntax-function">$1</span>'
  );

  return highlighted;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ============================================================================
// API INTEGRATION
// ============================================================================

/**
 * Call Anthropic API for code completion
 */
async function getCompletions(code, cursorInfo, language, apiKey, signal) {
  if (!apiKey) {
    // Return mock completions for demo
    return getMockCompletions(code, cursorInfo, language);
  }

  const prompt = `<instruction>
You are an expert code completion engine. Given the code context, suggest the most likely next code the developer intends to write.

Rules:
- Complete the current logical unit (statement, expression, block)
- Match the existing code style (indentation, naming conventions)
- Prefer idiomatic patterns for the detected language
- Never suggest code that would create syntax errors
- If uncertain, provide shorter, safer completions
</instruction>

<code_context>
Language: ${language}
File content before cursor:
\`\`\`
${cursorInfo.beforeCursor}
\`\`\`

Content after cursor (if any):
\`\`\`
${cursorInfo.afterCursor}
\`\`\`
</code_context>

<output_format>
Respond with JSON only:
{
  "suggestions": [
    {
      "text": "completion text",
      "confidence": 0.0-1.0,
      "explanation": "brief reason"
    }
  ],
  "detected_intent": "what the user is likely trying to do"
}
</output_format>`;

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1024,
        messages: [{ role: 'user', content: prompt }],
      }),
      signal,
    });

    if (!response.ok) throw new Error('API request failed');

    const data = await response.json();
    const content = data.content[0].text;

    // Parse JSON from response
    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
    throw new Error('Invalid response format');
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    console.error('Completion API error:', error);
    return getMockCompletions(code, cursorInfo, language);
  }
}

/**
 * Call Anthropic API for code analysis
 */
async function analyzeCode(code, language, apiKey, signal) {
  if (!apiKey) {
    return getMockAnalysis(code, language);
  }

  const prompt = `<instruction>
Analyze this code for errors, warnings, and improvement opportunities. Be precise about locations and severity.
</instruction>

<code>
Language: ${language}
\`\`\`
${code}
\`\`\`
</code>

<output_format>
{
  "diagnostics": [
    {
      "line": number,
      "column": number,
      "endColumn": number,
      "severity": "error" | "warning" | "info",
      "message": "clear, actionable message",
      "code": "ERROR_CODE",
      "fix": "suggested fix if applicable"
    }
  ],
  "context": {
    "currentFunction": "name and signature if in function",
    "imports": ["missing imports"],
    "suggestions": ["improvement ideas"]
  }
}
</output_format>`;

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 2048,
        messages: [{ role: 'user', content: prompt }],
      }),
      signal,
    });

    if (!response.ok) throw new Error('API request failed');

    const data = await response.json();
    const content = data.content[0].text;

    const jsonMatch = content.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      return JSON.parse(jsonMatch[0]);
    }
    throw new Error('Invalid response format');
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    console.error('Analysis API error:', error);
    return getMockAnalysis(code, language);
  }
}

/**
 * Mock completions for demo mode
 */
function getMockCompletions(code, cursorInfo, language) {
  const lastLine = cursorInfo.beforeCursor.split('\n').pop() || '';
  const suggestions = [];

  // Context-aware mock suggestions
  if (lastLine.includes('function') && lastLine.includes('(')) {
    suggestions.push({
      text: ') {\n  \n}',
      confidence: 0.9,
      explanation: 'Complete function declaration'
    });
  } else if (lastLine.trim().startsWith('return')) {
    suggestions.push({
      text: ' result;',
      confidence: 0.7,
      explanation: 'Return statement'
    });
  } else if (lastLine.includes('console.')) {
    suggestions.push({
      text: 'log()',
      confidence: 0.95,
      explanation: 'Console log method'
    });
  } else if (lastLine.includes('.map(')) {
    suggestions.push({
      text: '(item) => item)',
      confidence: 0.8,
      explanation: 'Map callback'
    });
  } else if (lastLine.includes('.filter(')) {
    suggestions.push({
      text: '(item) => item !== null)',
      confidence: 0.75,
      explanation: 'Filter callback'
    });
  } else if (lastLine.trim() === '') {
    suggestions.push({
      text: 'const ',
      confidence: 0.6,
      explanation: 'Start variable declaration'
    });
  } else if (lastLine.includes('if (')) {
    suggestions.push({
      text: ') {\n  \n}',
      confidence: 0.85,
      explanation: 'Complete if statement'
    });
  } else if (lastLine.includes('async ')) {
    suggestions.push({
      text: 'function fetchData() {\n  const response = await fetch();\n  return response.json();\n}',
      confidence: 0.7,
      explanation: 'Async function template'
    });
  }

  // Add a generic suggestion if we have none
  if (suggestions.length === 0) {
    suggestions.push({
      text: '// TODO: implement',
      confidence: 0.3,
      explanation: 'Placeholder comment'
    });
  }

  return {
    suggestions,
    detected_intent: 'Writing code'
  };
}

/**
 * Mock analysis for demo mode
 */
function getMockAnalysis(code, language) {
  const diagnostics = [];
  const lines = code.split('\n');

  lines.forEach((line, index) => {
    const lineNum = index + 1;

    // Check for common issues
    if (line.includes('var ') && (language === 'javascript' || language === 'typescript')) {
      diagnostics.push({
        line: lineNum,
        column: line.indexOf('var ') + 1,
        endColumn: line.indexOf('var ') + 4,
        severity: 'warning',
        message: 'Use "const" or "let" instead of "var"',
        code: 'NO_VAR',
        fix: line.replace('var ', 'const ')
      });
    }

    if (line.includes('console.log') && !line.trim().startsWith('//')) {
      diagnostics.push({
        line: lineNum,
        column: line.indexOf('console.log') + 1,
        endColumn: line.indexOf('console.log') + 11,
        severity: 'info',
        message: 'Remove console.log before production',
        code: 'NO_CONSOLE',
        fix: '// ' + line.trim()
      });
    }

    // Check for missing await
    if (line.includes('.json()') && !line.includes('await') &&
        code.includes('async')) {
      diagnostics.push({
        line: lineNum,
        column: line.indexOf('.json()') + 1,
        endColumn: line.indexOf('.json()') + 7,
        severity: 'error',
        message: 'Missing "await" before .json() in async context',
        code: 'MISSING_AWAIT',
        fix: line.replace('.json()', 'await .json()')
      });
    }

    // Check for unused variables (simple heuristic)
    const constMatch = line.match(/const\s+(\w+)\s*=/);
    if (constMatch) {
      const varName = constMatch[1];
      const restOfCode = code.split('\n').slice(index + 1).join('\n');
      if (!restOfCode.includes(varName)) {
        diagnostics.push({
          line: lineNum,
          column: line.indexOf(varName) + 1,
          endColumn: line.indexOf(varName) + varName.length + 1,
          severity: 'warning',
          message: `"${varName}" is defined but never used`,
          code: 'UNUSED_VAR',
          fix: null
        });
      }
    }

    // Python-specific checks
    if (language === 'python') {
      if (line.match(/def\s+\w+\([^)]*\)\s*$/) && !line.endsWith(':')) {
        diagnostics.push({
          line: lineNum,
          column: line.length,
          endColumn: line.length + 1,
          severity: 'error',
          message: 'Missing colon after function definition',
          code: 'SYNTAX_ERROR',
          fix: line + ':'
        });
      }
    }
  });

  return {
    diagnostics,
    context: {
      currentFunction: null,
      imports: [],
      suggestions: diagnostics.length === 0 ? ['Code looks good!'] : ['Consider fixing the issues above']
    }
  };
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function IntelligentCodeEditor({ apiKey = '' }) {
  // -------------------------------------------------------------------------
  // State Management
  // -------------------------------------------------------------------------
  const [code, setCode] = useState(SAMPLE_CODE);
  const [language, setLanguage] = useState('javascript');
  const [cursorPosition, setCursorPosition] = useState({ line: 1, column: 1 });
  const [suggestions, setSuggestions] = useState([]);
  const [selectedSuggestion, setSelectedSuggestion] = useState(0);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [ghostText, setGhostText] = useState('');
  const [diagnostics, setDiagnostics] = useState([]);
  const [contextInfo, setContextInfo] = useState(null);
  const [isLoadingCompletion, setIsLoadingCompletion] = useState(false);
  const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false);
  const [showIntelligencePanel, setShowIntelligencePanel] = useState(true);
  const [theme, setTheme] = useState('dark');
  const [hoveredError, setHoveredError] = useState(null);
  const [settings, setSettings] = useState({
    autoComplete: true,
    autoAnalyze: true,
    fontSize: 14,
    tabSize: 2,
  });

  // Refs
  const textareaRef = useRef(null);
  const completionAbortRef = useRef(null);
  const analysisAbortRef = useRef(null);
  const suggestionsRef = useRef(null);

  // Debounced values for API calls
  const debouncedCode = useDebounce(code, DEBOUNCE_ANALYSIS);
  const debouncedCursor = useDebounce(cursorPosition, DEBOUNCE_COMPLETION);

  // -------------------------------------------------------------------------
  // Language Detection
  // -------------------------------------------------------------------------
  useEffect(() => {
    const detected = detectLanguage(code);
    if (detected !== language) {
      setLanguage(detected);
    }
  }, [debouncedCode]);

  // -------------------------------------------------------------------------
  // Code Analysis Effect
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!settings.autoAnalyze) return;

    // Cancel previous request
    if (analysisAbortRef.current) {
      analysisAbortRef.current.abort();
    }

    const controller = new AbortController();
    analysisAbortRef.current = controller;

    setIsLoadingAnalysis(true);

    analyzeCode(code, language, apiKey, controller.signal)
      .then(result => {
        if (result && !controller.signal.aborted) {
          setDiagnostics(result.diagnostics || []);
          setContextInfo(result.context || null);
        }
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          console.error('Analysis error:', err);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoadingAnalysis(false);
        }
      });

    return () => controller.abort();
  }, [debouncedCode, language, apiKey, settings.autoAnalyze]);

  // -------------------------------------------------------------------------
  // Code Completion Effect
  // -------------------------------------------------------------------------
  const fetchCompletions = useCallback(async () => {
    if (!settings.autoComplete || !textareaRef.current) return;

    const cursorInfo = getCursorInfo(textareaRef.current);
    const lastChar = cursorInfo.beforeCursor.slice(-1);

    // Don't suggest after whitespace-only or at start of file
    if (!cursorInfo.beforeCursor.trim() || /^\s*$/.test(cursorInfo.beforeCursor.split('\n').pop())) {
      setShowSuggestions(false);
      setGhostText('');
      return;
    }

    // Cancel previous request
    if (completionAbortRef.current) {
      completionAbortRef.current.abort();
    }

    const controller = new AbortController();
    completionAbortRef.current = controller;

    setIsLoadingCompletion(true);

    try {
      const result = await getCompletions(code, cursorInfo, language, apiKey, controller.signal);

      if (result && result.suggestions && result.suggestions.length > 0 && !controller.signal.aborted) {
        setSuggestions(result.suggestions);
        setSelectedSuggestion(0);
        setShowSuggestions(true);
        setGhostText(result.suggestions[0].text);
      } else {
        setShowSuggestions(false);
        setGhostText('');
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('Completion error:', err);
      }
    } finally {
      if (!controller.signal.aborted) {
        setIsLoadingCompletion(false);
      }
    }
  }, [code, language, apiKey, settings.autoComplete]);

  // Trigger completions after cursor movement/typing stops
  useEffect(() => {
    const timer = setTimeout(fetchCompletions, DEBOUNCE_COMPLETION);
    return () => clearTimeout(timer);
  }, [debouncedCursor, fetchCompletions]);

  // -------------------------------------------------------------------------
  // Event Handlers
  // -------------------------------------------------------------------------
  const handleCodeChange = useCallback((e) => {
    setCode(e.target.value);
  }, []);

  const handleCursorChange = useCallback(() => {
    if (!textareaRef.current) return;
    const { line, column } = getCursorInfo(textareaRef.current);
    setCursorPosition({ line, column });
  }, []);

  const handleKeyDown = useCallback((e) => {
    // Handle suggestion navigation
    if (showSuggestions) {
      if (e.key === 'Tab') {
        e.preventDefault();
        acceptSuggestion();
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        dismissSuggestions();
        return;
      }
      if (e.key === 'ArrowDown' || (e.ctrlKey && e.key === 'n')) {
        e.preventDefault();
        setSelectedSuggestion(prev =>
          Math.min(prev + 1, suggestions.length - 1));
        return;
      }
      if (e.key === 'ArrowUp' || (e.ctrlKey && e.key === 'p')) {
        e.preventDefault();
        setSelectedSuggestion(prev => Math.max(prev - 1, 0));
        return;
      }
    }

    // Global shortcuts
    if (e.ctrlKey && e.key === ' ') {
      e.preventDefault();
      fetchCompletions();
      return;
    }

    if (e.ctrlKey && e.key === 'i') {
      e.preventDefault();
      setShowIntelligencePanel(prev => !prev);
      return;
    }

    if (e.key === 'F8') {
      e.preventDefault();
      goToNextError();
      return;
    }

    if (e.ctrlKey && e.key === '.') {
      e.preventDefault();
      applyQuickFix();
      return;
    }
  }, [showSuggestions, suggestions, fetchCompletions]);

  const acceptSuggestion = useCallback(() => {
    if (suggestions.length === 0 || !textareaRef.current) return;

    const suggestion = suggestions[selectedSuggestion];
    const textarea = textareaRef.current;
    const { selectionStart, value } = textarea;

    const newCode = value.substring(0, selectionStart) +
                   suggestion.text +
                   value.substring(selectionStart);

    setCode(newCode);
    setShowSuggestions(false);
    setGhostText('');

    // Move cursor after inserted text
    setTimeout(() => {
      if (textareaRef.current) {
        const newPos = selectionStart + suggestion.text.length;
        textareaRef.current.selectionStart = newPos;
        textareaRef.current.selectionEnd = newPos;
        textareaRef.current.focus();
      }
    }, 0);
  }, [suggestions, selectedSuggestion]);

  const dismissSuggestions = useCallback(() => {
    setShowSuggestions(false);
    setGhostText('');
    setSuggestions([]);
  }, []);

  const goToNextError = useCallback(() => {
    if (diagnostics.length === 0 || !textareaRef.current) return;

    const currentLine = cursorPosition.line;
    const nextError = diagnostics.find(d => d.line > currentLine) || diagnostics[0];

    if (nextError) {
      // Calculate position to move cursor
      const lines = code.split('\n');
      let pos = 0;
      for (let i = 0; i < nextError.line - 1; i++) {
        pos += lines[i].length + 1;
      }
      pos += nextError.column - 1;

      textareaRef.current.selectionStart = pos;
      textareaRef.current.selectionEnd = pos;
      textareaRef.current.focus();
      handleCursorChange();
    }
  }, [diagnostics, cursorPosition, code, handleCursorChange]);

  const applyQuickFix = useCallback(() => {
    const errorOnLine = diagnostics.find(d => d.line === cursorPosition.line && d.fix);
    if (!errorOnLine) return;

    const lines = code.split('\n');
    lines[errorOnLine.line - 1] = errorOnLine.fix;
    setCode(lines.join('\n'));
  }, [diagnostics, cursorPosition, code]);

  // Update ghost text when selection changes
  useEffect(() => {
    if (suggestions.length > 0 && showSuggestions) {
      setGhostText(suggestions[selectedSuggestion].text);
    }
  }, [selectedSuggestion, suggestions, showSuggestions]);

  // -------------------------------------------------------------------------
  // Computed Values
  // -------------------------------------------------------------------------
  const errorCount = useMemo(() =>
    diagnostics.filter(d => d.severity === 'error').length, [diagnostics]);
  const warningCount = useMemo(() =>
    diagnostics.filter(d => d.severity === 'warning').length, [diagnostics]);
  const infoCount = useMemo(() =>
    diagnostics.filter(d => d.severity === 'info').length, [diagnostics]);

  const highlightedCode = useMemo(() =>
    highlightCode(code, language), [code, language]);

  const lineNumbers = useMemo(() =>
    code.split('\n').map((_, i) => i + 1), [code]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <div className={`editor-container ${theme}`} style={styles.container}>
      {/* Toolbar */}
      <div style={styles.toolbar}>
        <div style={styles.toolbarLeft}>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            style={styles.select}
          >
            {Object.entries(LANGUAGES).map(([key, { name }]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>

          <button
            onClick={() => setShowIntelligencePanel(p => !p)}
            style={{
              ...styles.button,
              backgroundColor: showIntelligencePanel ? '#89b4fa' : 'transparent',
              color: showIntelligencePanel ? '#1e1e2e' : '#cdd6f4',
            }}
            title="Toggle Intelligence Panel (Ctrl+I)"
          >
            🧠 Intelligence
          </button>
        </div>

        <div style={styles.toolbarRight}>
          <label style={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={settings.autoComplete}
              onChange={(e) => setSettings(s => ({ ...s, autoComplete: e.target.checked }))}
            />
            Auto-complete
          </label>
          <label style={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={settings.autoAnalyze}
              onChange={(e) => setSettings(s => ({ ...s, autoAnalyze: e.target.checked }))}
            />
            Auto-analyze
          </label>

          <button
            onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            style={styles.button}
            title="Toggle Theme"
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
        </div>
      </div>

      {/* Main Editor Area */}
      <div style={styles.mainArea}>
        {/* Code Editor */}
        <div style={styles.editorPane}>
          <div style={styles.editorWrapper}>
            {/* Line Numbers */}
            <div style={styles.lineNumbers}>
              {lineNumbers.map(num => (
                <div
                  key={num}
                  style={{
                    ...styles.lineNumber,
                    backgroundColor: diagnostics.some(d => d.line === num && d.severity === 'error')
                      ? 'rgba(243, 139, 168, 0.2)'
                      : diagnostics.some(d => d.line === num && d.severity === 'warning')
                      ? 'rgba(250, 179, 135, 0.1)'
                      : 'transparent',
                  }}
                >
                  {num}
                </div>
              ))}
            </div>

            {/* Code Area */}
            <div style={styles.codeArea}>
              {/* Syntax Highlighted Layer */}
              <pre
                style={styles.highlightedCode}
                dangerouslySetInnerHTML={{ __html: highlightedCode }}
              />

              {/* Error Underlines */}
              <div style={styles.errorLayer}>
                {diagnostics.map((diag, idx) => (
                  <ErrorHighlight
                    key={idx}
                    diagnostic={diag}
                    code={code}
                    fontSize={settings.fontSize}
                    onHover={setHoveredError}
                  />
                ))}
              </div>

              {/* Ghost Text */}
              {ghostText && showSuggestions && (
                <GhostTextOverlay
                  code={code}
                  ghostText={ghostText}
                  cursorPosition={getCursorInfo(textareaRef.current || { selectionStart: 0, value: '' })}
                  fontSize={settings.fontSize}
                />
              )}

              {/* Actual Textarea */}
              <textarea
                ref={textareaRef}
                value={code}
                onChange={handleCodeChange}
                onKeyDown={handleKeyDown}
                onSelect={handleCursorChange}
                onClick={handleCursorChange}
                style={{
                  ...styles.textarea,
                  fontSize: settings.fontSize,
                }}
                spellCheck={false}
                autoCapitalize="off"
                autoComplete="off"
                autoCorrect="off"
              />
            </div>
          </div>

          {/* Suggestions Popup */}
          {showSuggestions && suggestions.length > 0 && (
            <SuggestionsPopup
              suggestions={suggestions}
              selectedIndex={selectedSuggestion}
              onSelect={(idx) => {
                setSelectedSuggestion(idx);
                acceptSuggestion();
              }}
              onHover={setSelectedSuggestion}
              position={calculatePopupPosition(textareaRef.current, cursorPosition)}
            />
          )}

          {/* Error Tooltip */}
          {hoveredError && (
            <ErrorTooltip
              diagnostic={hoveredError}
              onApplyFix={() => {
                if (hoveredError.fix) {
                  const lines = code.split('\n');
                  lines[hoveredError.line - 1] = hoveredError.fix;
                  setCode(lines.join('\n'));
                  setHoveredError(null);
                }
              }}
            />
          )}
        </div>

        {/* Intelligence Panel */}
        {showIntelligencePanel && (
          <div style={styles.intelligencePanel}>
            <IntelligencePanel
              diagnostics={diagnostics}
              contextInfo={contextInfo}
              cursorPosition={cursorPosition}
              code={code}
              language={language}
              isLoading={isLoadingAnalysis}
              onGoToError={(diag) => {
                const lines = code.split('\n');
                let pos = 0;
                for (let i = 0; i < diag.line - 1; i++) {
                  pos += lines[i].length + 1;
                }
                pos += diag.column - 1;
                if (textareaRef.current) {
                  textareaRef.current.selectionStart = pos;
                  textareaRef.current.selectionEnd = pos;
                  textareaRef.current.focus();
                  handleCursorChange();
                }
              }}
            />
          </div>
        )}
      </div>

      {/* Status Bar */}
      <div style={styles.statusBar}>
        <div style={styles.statusLeft}>
          <span style={styles.statusItem}>
            {LANGUAGES[language]?.icon || 'TXT'} {LANGUAGES[language]?.name || language}
          </span>
          <span style={styles.statusItem}>
            Ln {cursorPosition.line}, Col {cursorPosition.column}
          </span>
        </div>

        <div style={styles.statusRight}>
          {isLoadingCompletion && (
            <span style={{ ...styles.statusItem, color: '#89b4fa' }}>
              ⟳ Getting suggestions...
            </span>
          )}
          {isLoadingAnalysis && (
            <span style={{ ...styles.statusItem, color: '#89b4fa' }}>
              ⟳ Analyzing...
            </span>
          )}
          {errorCount > 0 && (
            <span style={{ ...styles.statusItem, color: '#f38ba8' }}>
              ✕ {errorCount} error{errorCount > 1 ? 's' : ''}
            </span>
          )}
          {warningCount > 0 && (
            <span style={{ ...styles.statusItem, color: '#fab387' }}>
              ⚠ {warningCount} warning{warningCount > 1 ? 's' : ''}
            </span>
          )}
          {infoCount > 0 && (
            <span style={{ ...styles.statusItem, color: '#89dceb' }}>
              ℹ {infoCount} hint{infoCount > 1 ? 's' : ''}
            </span>
          )}
          {errorCount === 0 && warningCount === 0 && !isLoadingAnalysis && (
            <span style={{ ...styles.statusItem, color: '#a6e3a1' }}>
              ✓ No issues
            </span>
          )}
        </div>
      </div>

      <style>{globalStyles}</style>
    </div>
  );
}

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

/**
 * Suggestions popup component
 */
function SuggestionsPopup({ suggestions, selectedIndex, onSelect, onHover, position }) {
  return (
    <div
      style={{
        ...styles.suggestionsPopup,
        top: position.top,
        left: position.left,
      }}
    >
      {suggestions.map((suggestion, idx) => (
        <div
          key={idx}
          style={{
            ...styles.suggestionItem,
            backgroundColor: idx === selectedIndex ? '#45475a' : 'transparent',
          }}
          onClick={() => onSelect(idx)}
          onMouseEnter={() => onHover(idx)}
        >
          <div style={styles.suggestionText}>
            <code style={styles.suggestionCode}>
              {suggestion.text.length > 50
                ? suggestion.text.substring(0, 50) + '...'
                : suggestion.text}
            </code>
          </div>
          <div style={styles.suggestionMeta}>
            <span style={styles.confidence}>
              {Math.round(suggestion.confidence * 100)}%
            </span>
            <span style={styles.explanation}>
              {suggestion.explanation}
            </span>
          </div>
        </div>
      ))}
      <div style={styles.suggestionHint}>
        Tab to accept • Esc to dismiss • ↑↓ to navigate
      </div>
    </div>
  );
}

/**
 * Ghost text overlay for showing inline completion preview
 */
function GhostTextOverlay({ code, ghostText, cursorPosition, fontSize }) {
  if (!cursorPosition) return null;

  const lines = code.split('\n');
  const currentLineIndex = cursorPosition.line - 1;

  return (
    <div style={{ ...styles.ghostTextOverlay, fontSize }}>
      {lines.map((line, idx) => (
        <div key={idx} style={styles.ghostTextLine}>
          {idx === currentLineIndex && (
            <>
              <span style={{ visibility: 'hidden' }}>
                {line.substring(0, cursorPosition.column - 1)}
              </span>
              <span style={styles.ghostText}>{ghostText}</span>
            </>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Error highlight underline
 */
function ErrorHighlight({ diagnostic, code, fontSize, onHover }) {
  const lines = code.split('\n');
  const lineContent = lines[diagnostic.line - 1] || '';
  const startCol = diagnostic.column - 1;
  const endCol = diagnostic.endColumn ? diagnostic.endColumn - 1 : startCol + 5;

  const lineHeight = fontSize * 1.5;
  const charWidth = fontSize * 0.6;

  return (
    <div
      style={{
        position: 'absolute',
        top: (diagnostic.line - 1) * lineHeight,
        left: startCol * charWidth,
        width: Math.max((endCol - startCol) * charWidth, 20),
        height: 2,
        backgroundColor: SEVERITY_COLORS[diagnostic.severity]?.border || '#f38ba8',
        opacity: 0.8,
        cursor: 'pointer',
      }}
      onMouseEnter={() => onHover(diagnostic)}
      onMouseLeave={() => onHover(null)}
    />
  );
}

/**
 * Error tooltip
 */
function ErrorTooltip({ diagnostic, onApplyFix }) {
  return (
    <div style={styles.errorTooltip}>
      <div style={{
        ...styles.tooltipHeader,
        color: SEVERITY_COLORS[diagnostic.severity]?.text,
      }}>
        {diagnostic.severity === 'error' ? '✕' : diagnostic.severity === 'warning' ? '⚠' : 'ℹ'}
        {' '}{diagnostic.code}
      </div>
      <div style={styles.tooltipMessage}>
        {diagnostic.message}
      </div>
      {diagnostic.fix && (
        <button
          style={styles.quickFixButton}
          onClick={onApplyFix}
        >
          Apply Quick Fix
        </button>
      )}
    </div>
  );
}

/**
 * Intelligence panel showing context and analysis
 */
function IntelligencePanel({
  diagnostics,
  contextInfo,
  cursorPosition,
  code,
  language,
  isLoading,
  onGoToError
}) {
  const [activeTab, setActiveTab] = useState('errors');

  const tabs = [
    { id: 'errors', label: 'Problems', count: diagnostics.length },
    { id: 'context', label: 'Context', count: null },
    { id: 'suggestions', label: 'Hints', count: contextInfo?.suggestions?.length || 0 },
  ];

  return (
    <div style={styles.panelContainer}>
      <div style={styles.panelTabs}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            style={{
              ...styles.panelTab,
              borderBottom: activeTab === tab.id ? '2px solid #89b4fa' : '2px solid transparent',
              color: activeTab === tab.id ? '#cdd6f4' : '#a6adc8',
            }}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
            {tab.count !== null && tab.count > 0 && (
              <span style={styles.tabBadge}>{tab.count}</span>
            )}
          </button>
        ))}
      </div>

      <div style={styles.panelContent}>
        {isLoading && (
          <div style={styles.loadingIndicator}>
            Analyzing code...
          </div>
        )}

        {activeTab === 'errors' && (
          <div style={styles.errorList}>
            {diagnostics.length === 0 ? (
              <div style={styles.emptyState}>
                ✓ No problems detected
              </div>
            ) : (
              diagnostics.map((diag, idx) => (
                <div
                  key={idx}
                  style={styles.errorItem}
                  onClick={() => onGoToError(diag)}
                >
                  <span style={{
                    ...styles.errorIcon,
                    color: SEVERITY_COLORS[diag.severity]?.text,
                  }}>
                    {diag.severity === 'error' ? '✕' : diag.severity === 'warning' ? '⚠' : 'ℹ'}
                  </span>
                  <div style={styles.errorContent}>
                    <div style={styles.errorMessage}>{diag.message}</div>
                    <div style={styles.errorLocation}>
                      Line {diag.line}, Col {diag.column}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'context' && (
          <div style={styles.contextSection}>
            <div style={styles.contextItem}>
              <div style={styles.contextLabel}>Language</div>
              <div style={styles.contextValue}>
                {LANGUAGES[language]?.name || language}
              </div>
            </div>
            <div style={styles.contextItem}>
              <div style={styles.contextLabel}>Current Position</div>
              <div style={styles.contextValue}>
                Line {cursorPosition.line}, Column {cursorPosition.column}
              </div>
            </div>
            {contextInfo?.currentFunction && (
              <div style={styles.contextItem}>
                <div style={styles.contextLabel}>Current Function</div>
                <div style={styles.contextValue}>
                  <code>{contextInfo.currentFunction}</code>
                </div>
              </div>
            )}
            {contextInfo?.imports?.length > 0 && (
              <div style={styles.contextItem}>
                <div style={styles.contextLabel}>Missing Imports</div>
                <div style={styles.contextValue}>
                  {contextInfo.imports.map((imp, idx) => (
                    <div key={idx}><code>{imp}</code></div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'suggestions' && (
          <div style={styles.suggestionsList}>
            {(!contextInfo?.suggestions || contextInfo.suggestions.length === 0) ? (
              <div style={styles.emptyState}>
                No suggestions at this time
              </div>
            ) : (
              contextInfo.suggestions.map((suggestion, idx) => (
                <div key={idx} style={styles.suggestionCard}>
                  <span style={styles.suggestionIcon}>💡</span>
                  <span>{suggestion}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Keyboard shortcuts reference */}
      <div style={styles.shortcutsPanel}>
        <div style={styles.shortcutsTitle}>Keyboard Shortcuts</div>
        <div style={styles.shortcutItem}>
          <kbd style={styles.kbd}>Tab</kbd> Accept suggestion
        </div>
        <div style={styles.shortcutItem}>
          <kbd style={styles.kbd}>Esc</kbd> Dismiss
        </div>
        <div style={styles.shortcutItem}>
          <kbd style={styles.kbd}>Ctrl+Space</kbd> Trigger completion
        </div>
        <div style={styles.shortcutItem}>
          <kbd style={styles.kbd}>F8</kbd> Next error
        </div>
        <div style={styles.shortcutItem}>
          <kbd style={styles.kbd}>Ctrl+.</kbd> Quick fix
        </div>
      </div>
    </div>
  );
}

/**
 * Calculate popup position based on cursor
 */
function calculatePopupPosition(textarea, cursorPosition) {
  if (!textarea) return { top: 100, left: 100 };

  const lineHeight = 21;
  const charWidth = 8.4;

  return {
    top: cursorPosition.line * lineHeight + 60, // Account for toolbar
    left: Math.min(cursorPosition.column * charWidth + 50, 400), // Line numbers offset
  };
}

// ============================================================================
// STYLES
// ============================================================================

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    backgroundColor: '#1e1e2e',
    color: '#cdd6f4',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  },

  toolbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px 16px',
    backgroundColor: '#181825',
    borderBottom: '1px solid #313244',
  },

  toolbarLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },

  toolbarRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },

  select: {
    backgroundColor: '#313244',
    color: '#cdd6f4',
    border: '1px solid #45475a',
    borderRadius: '4px',
    padding: '6px 12px',
    fontSize: '13px',
    cursor: 'pointer',
  },

  button: {
    backgroundColor: 'transparent',
    color: '#cdd6f4',
    border: '1px solid #45475a',
    borderRadius: '4px',
    padding: '6px 12px',
    fontSize: '13px',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },

  checkboxLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '13px',
    color: '#a6adc8',
    cursor: 'pointer',
  },

  mainArea: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },

  editorPane: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    overflow: 'hidden',
  },

  editorWrapper: {
    display: 'flex',
    flex: 1,
    overflow: 'auto',
  },

  lineNumbers: {
    backgroundColor: '#181825',
    padding: '12px 0',
    textAlign: 'right',
    userSelect: 'none',
    minWidth: '50px',
    borderRight: '1px solid #313244',
  },

  lineNumber: {
    padding: '0 12px',
    fontSize: '14px',
    lineHeight: '21px',
    color: '#6c7086',
  },

  codeArea: {
    flex: 1,
    position: 'relative',
    padding: '12px',
    overflow: 'auto',
  },

  highlightedCode: {
    position: 'absolute',
    top: '12px',
    left: '12px',
    right: '12px',
    margin: 0,
    padding: 0,
    fontSize: '14px',
    lineHeight: '21px',
    fontFamily: '"Fira Code", "Consolas", "Monaco", monospace',
    whiteSpace: 'pre',
    pointerEvents: 'none',
    color: '#cdd6f4',
  },

  errorLayer: {
    position: 'absolute',
    top: '12px',
    left: '12px',
    right: '12px',
    pointerEvents: 'auto',
  },

  ghostTextOverlay: {
    position: 'absolute',
    top: '12px',
    left: '12px',
    right: '12px',
    pointerEvents: 'none',
    fontFamily: '"Fira Code", "Consolas", "Monaco", monospace',
    lineHeight: '21px',
    whiteSpace: 'pre',
  },

  ghostTextLine: {
    height: '21px',
  },

  ghostText: {
    color: '#6c7086',
    opacity: 0.6,
  },

  textarea: {
    position: 'relative',
    width: '100%',
    height: '100%',
    minHeight: '400px',
    backgroundColor: 'transparent',
    color: 'transparent',
    caretColor: '#89b4fa',
    border: 'none',
    outline: 'none',
    resize: 'none',
    fontFamily: '"Fira Code", "Consolas", "Monaco", monospace',
    lineHeight: '21px',
    padding: 0,
    margin: 0,
  },

  suggestionsPopup: {
    position: 'absolute',
    backgroundColor: '#313244',
    border: '1px solid #45475a',
    borderRadius: '6px',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
    zIndex: 1000,
    maxWidth: '500px',
    minWidth: '300px',
    overflow: 'hidden',
  },

  suggestionItem: {
    padding: '8px 12px',
    cursor: 'pointer',
    borderBottom: '1px solid #45475a',
    transition: 'background-color 0.1s ease',
  },

  suggestionText: {
    marginBottom: '4px',
  },

  suggestionCode: {
    fontSize: '13px',
    fontFamily: '"Fira Code", "Consolas", monospace',
    color: '#cdd6f4',
  },

  suggestionMeta: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '11px',
  },

  confidence: {
    backgroundColor: '#45475a',
    padding: '2px 6px',
    borderRadius: '3px',
    color: '#a6e3a1',
  },

  explanation: {
    color: '#6c7086',
    marginLeft: '8px',
  },

  suggestionHint: {
    padding: '6px 12px',
    fontSize: '11px',
    color: '#6c7086',
    backgroundColor: '#181825',
    textAlign: 'center',
  },

  errorTooltip: {
    position: 'fixed',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    backgroundColor: '#313244',
    border: '1px solid #45475a',
    borderRadius: '8px',
    padding: '16px',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
    zIndex: 1001,
    maxWidth: '400px',
  },

  tooltipHeader: {
    fontSize: '14px',
    fontWeight: 'bold',
    marginBottom: '8px',
  },

  tooltipMessage: {
    fontSize: '13px',
    color: '#cdd6f4',
    marginBottom: '12px',
  },

  quickFixButton: {
    backgroundColor: '#89b4fa',
    color: '#1e1e2e',
    border: 'none',
    borderRadius: '4px',
    padding: '8px 16px',
    fontSize: '13px',
    cursor: 'pointer',
    fontWeight: 'bold',
  },

  intelligencePanel: {
    width: '320px',
    backgroundColor: '#181825',
    borderLeft: '1px solid #313244',
    display: 'flex',
    flexDirection: 'column',
  },

  panelContainer: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
  },

  panelTabs: {
    display: 'flex',
    borderBottom: '1px solid #313244',
  },

  panelTab: {
    flex: 1,
    padding: '12px 8px',
    backgroundColor: 'transparent',
    border: 'none',
    cursor: 'pointer',
    fontSize: '12px',
    fontWeight: '500',
    transition: 'all 0.15s ease',
  },

  tabBadge: {
    backgroundColor: '#45475a',
    padding: '2px 6px',
    borderRadius: '10px',
    fontSize: '10px',
    marginLeft: '6px',
  },

  panelContent: {
    flex: 1,
    overflow: 'auto',
    padding: '12px',
  },

  loadingIndicator: {
    textAlign: 'center',
    padding: '20px',
    color: '#6c7086',
    fontSize: '13px',
  },

  errorList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },

  errorItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    padding: '10px',
    backgroundColor: '#313244',
    borderRadius: '6px',
    cursor: 'pointer',
    transition: 'background-color 0.15s ease',
  },

  errorIcon: {
    fontSize: '14px',
    marginTop: '2px',
  },

  errorContent: {
    flex: 1,
  },

  errorMessage: {
    fontSize: '13px',
    color: '#cdd6f4',
    marginBottom: '4px',
  },

  errorLocation: {
    fontSize: '11px',
    color: '#6c7086',
  },

  emptyState: {
    textAlign: 'center',
    padding: '30px',
    color: '#a6e3a1',
    fontSize: '13px',
  },

  contextSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },

  contextItem: {
    borderBottom: '1px solid #313244',
    paddingBottom: '12px',
  },

  contextLabel: {
    fontSize: '11px',
    color: '#6c7086',
    marginBottom: '4px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },

  contextValue: {
    fontSize: '13px',
    color: '#cdd6f4',
  },

  suggestionsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },

  suggestionCard: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    padding: '10px',
    backgroundColor: '#313244',
    borderRadius: '6px',
    fontSize: '13px',
  },

  suggestionIcon: {
    fontSize: '14px',
  },

  shortcutsPanel: {
    padding: '12px',
    borderTop: '1px solid #313244',
    backgroundColor: '#181825',
  },

  shortcutsTitle: {
    fontSize: '11px',
    color: '#6c7086',
    marginBottom: '8px',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },

  shortcutItem: {
    fontSize: '12px',
    color: '#a6adc8',
    marginBottom: '6px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },

  kbd: {
    backgroundColor: '#313244',
    padding: '2px 6px',
    borderRadius: '3px',
    fontSize: '11px',
    fontFamily: 'monospace',
    color: '#cdd6f4',
    border: '1px solid #45475a',
  },

  statusBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '6px 16px',
    backgroundColor: '#181825',
    borderTop: '1px solid #313244',
    fontSize: '12px',
  },

  statusLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },

  statusRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },

  statusItem: {
    color: '#6c7086',
  },
};

const globalStyles = `
  .syntax-keyword {
    color: #cba6f7;
    font-weight: 500;
  }

  .syntax-string {
    color: #a6e3a1;
  }

  .syntax-comment {
    color: #6c7086;
    font-style: italic;
  }

  .syntax-number {
    color: #fab387;
  }

  .syntax-function {
    color: #89b4fa;
  }

  .syntax-type {
    color: #f9e2af;
  }

  * {
    box-sizing: border-box;
  }

  ::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  ::-webkit-scrollbar-track {
    background: #181825;
  }

  ::-webkit-scrollbar-thumb {
    background: #45475a;
    border-radius: 4px;
  }

  ::-webkit-scrollbar-thumb:hover {
    background: #585b70;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
  }
`;
