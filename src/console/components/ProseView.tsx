"use client"

import React from "react"
import ReactMarkdown from "react-markdown"
import remarkMath from "remark-math"
import rehypeKatex from "rehype-katex"
import "katex/dist/katex.min.css"

interface ProseViewProps {
  content: string
  className?: string
}

export function ProseView({ content, className }: ProseViewProps) {
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          p: ({ node, ...props }) => <p className="mb-2 leading-relaxed" {...props} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
