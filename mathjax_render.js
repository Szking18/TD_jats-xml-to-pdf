/**
 * MathML → SVG 转换脚本
 * 使用 MathJax 将 MathML 字符串渲染为 SVG
 *
 * 用法: node mathjax_render.js '<math>...</math>' <display|inline>
 * 输出: SVG 字符串 (stdout)
 */

const { mathjax } = require('mathjax-full/js/mathjax.js');
const { MathML } = require('mathjax-full/js/input/mathml.js');
const { SVG } = require('mathjax-full/js/output/svg.js');
const { liteAdaptor } = require('mathjax-full/js/adaptors/liteAdaptor.js');
const { RegisterHTMLHandler } = require('mathjax-full/js/handlers/html.js');
const { AllPackages } = require('mathjax-full/js/input/tex/AllPackages.js');

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);

const html = mathjax.document('', {
  InputJax: new MathML({ parseAs: 'html' }),
  OutputJax: new SVG({
    fontCache: 'local',
    scale: 1,
    minScale: 0.5,
  }),
});

// 从 stdin 读取 MathML
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (chunk) => {
  input += chunk;
});
process.stdin.on('end', () => {
  try {
    const display = process.argv[2] === 'display';
    const node = html.convert(input, { display: display });
    const svg = adaptor.outerHTML(node);
    // 去掉 XML 声明，只保留 SVG
    const svgMatch = svg.match(/<svg[\s\S]*<\/svg>/);
    if (svgMatch) {
      console.log(svgMatch[0]);
    } else {
      console.log(svg);
    }
  } catch (err) {
    // 出错时输出原始 MathML
    console.error('MathJax error:', err.message);
    console.log(input);
  }
});
