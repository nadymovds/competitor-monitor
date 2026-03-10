import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'fs'
import path from 'path'
import { execSync } from 'child_process'

export default defineConfig(({ command }) => {
  const pkgPath = path.resolve('./package.json')
  const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'))

  if (command === 'build') {
    const parts = pkg.version.split('.').map(Number)
    parts[2] += 1
    pkg.version = parts.join('.')
    fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n')

    if (!process.env.CI) {
      try {
        execSync(`git add "${pkgPath}"`, { stdio: 'inherit' })
        execSync(`git commit -m "chore: bump version to ${pkg.version}"`, { stdio: 'inherit' })
        execSync('git push', { stdio: 'inherit' })
      } catch (e) {
        // ignore git errors (e.g. nothing to commit)
      }
    }
  }

  return {
    plugins: [react()],
    base: '/competitor-monitor/',
    define: {
      'import.meta.env.VITE_APP_VERSION': JSON.stringify(pkg.version)
    },
    build: {
      outDir: 'dist',
      sourcemap: false
    },
    server: {
      port: 3000,
      open: true
    }
  }
})
