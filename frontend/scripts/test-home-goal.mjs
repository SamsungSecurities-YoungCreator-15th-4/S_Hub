// 기존 TypeScript + Node 내장 테스트 러너로 검증한다. 새 테스트 의존성은 필요 없다.
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const output = mkdtempSync(join(tmpdir(), "s-hub-home-goal-"));
try {
  const compile = spawnSync(process.execPath, [
    "node_modules/typescript/bin/tsc", "lib/home-goal/homeGoal.test.ts",
    "--outDir", output, "--module", "commonjs", "--target", "ES2017",
    "--esModuleInterop", "--skipLibCheck", "--strict", "--moduleResolution", "node",
  ], { stdio: "inherit" });
  if (compile.status !== 0) process.exitCode = compile.status ?? 1;
  else {
    const run = spawnSync(process.execPath, ["--test", join(output, "home-goal/homeGoal.test.js")], { stdio: "inherit" });
    process.exitCode = run.status ?? 1;
  }
} finally {
  rmSync(output, { recursive: true, force: true });
}
