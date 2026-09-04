#!/usr/bin/env node

/**
 * Archify 渲染輔助腳本
 * 用法: node .agents/skills/archify/scripts/render_diagram.js <type> <spec.json> <output.html>
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const [,, type, specFile, outputFile] = process.argv;

if (!type || !specFile || !outputFile) {
  console.error("用法: node render_diagram.js <workflow|architecture|sequence|dataflow> <spec.json> <output.html>");
  process.exit(1);
}

const engineBin = path.resolve(__dirname, '../../../../.archify-engine/archify/bin/archify.mjs');

if (!fs.existsSync(engineBin)) {
  console.error(`[錯誤] 找不到 Archify 引擎: ${engineBin}`);
  console.error("請確認 .archify-engine 已成功 clone 到專案根目錄。");
  process.exit(1);
}

console.log(`[1/2] 執行 Archify 幾何與排版驗證 (${type})...`);
try {
  const validateOutput = execSync(`node "${engineBin}" validate ${type} "${specFile}" --quality showcase --json`, { encoding: 'utf-8' });
  const result = JSON.parse(validateOutput);
  if (!result.ok) {
    console.error("[驗證失敗]", result.error);
    process.exit(1);
  }
  console.log(`[驗證通過] 9 項幾何檢查全數合格 (0 errors, 0 warnings)`);
} catch (err) {
  console.error("[驗證執行異常]", err.stdout || err.message);
  process.exit(1);
}

console.log(`[2/2] 編譯並交付最終 HTML (${outputFile})...`);
try {
  const deliverOutput = execSync(`node "${engineBin}" deliver ${type} "${specFile}" "${outputFile}" --quality showcase --json`, { encoding: 'utf-8' });
  const result = JSON.parse(deliverOutput);
  if (!result.ok) {
    console.error("[交付失敗]", result.error);
    process.exit(1);
  }
  console.log(`[成功交付] HTML 已生成: ${outputFile} (大小: ${result.artifact.bytes} bytes)`);
} catch (err) {
  console.error("[交付執行異常]", err.stdout || err.message);
  process.exit(1);
}
