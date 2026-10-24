// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import MarkdownContent from "../src/components/MarkdownContent.vue";

describe("MarkdownContent", () => {
  it("renders supported assistant Markdown", () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: "## Recovery\n\nUse the **runbook** and `restart-api`." }
    });

    expect(wrapper.find("h2").text()).toBe("Recovery");
    expect(wrapper.find("strong").text()).toBe("runbook");
    expect(wrapper.find("code").text()).toBe("restart-api");
  });

  it("removes untrusted raw HTML from assistant Markdown", () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: "Safe text <img src=x onerror=alert(1)>" }
    });

    expect(wrapper.html()).not.toContain("<img");
    expect(wrapper.text()).toContain("Safe text");
  });

  it("renders inline LaTeX formulas through KaTeX and DOMPurify", () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: "复杂度是 $O(N \\log N)$ 级别。" }
    });

    expect(wrapper.find(".katex").exists()).toBe(true);
    expect(wrapper.text()).toContain("O(NlogN)");
    expect(wrapper.text()).not.toContain("$O(N");
  });

  it("renders display LaTeX formulas and survives sanitization", () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: "$$\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}$$" }
    });

    expect(wrapper.find(".katex-display").exists()).toBe(true);
    expect(wrapper.find(".katex .katex-html").exists()).toBe(true);
    expect(wrapper.text()).not.toContain("$$");
  });

  it("leaves unmatched dollar signs as plain text instead of throwing", () => {
    const wrapper = mount(MarkdownContent, {
      props: { content: "这件商品价格是 $5 和 $10，未闭合公式 $O(N" }
    });

    expect(wrapper.find(".katex").exists()).toBe(false);
    expect(wrapper.text()).toContain("$5 和 $10");
  });
});
