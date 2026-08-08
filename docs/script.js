document.addEventListener("DOMContentLoaded", () => {
    // Typing effect for the terminal
    const terminalText = document.getElementById("terminal-text");
    
    if (terminalText) {
        const lines = [
            { type: 'input', text: 'processscope attach --name nginx' },
            { type: 'output', text: 'Initializing hook for process [nginx] (PID: 13337)...' },
            { type: 'success', text: '[OK] Attached to process via eBPF.' },
            { type: 'output', text: 'Starting telemetry engines...' },
            { type: 'success', text: '[OK] CPU Profiler active.' },
            { type: 'success', text: '[OK] Memory Tracker active.' },
            { type: 'output', text: 'Dashboard running at http://localhost:9876' }
        ];

        let currentLine = 0;
        
        function typeLine(lineObj, callback) {
            const lineElem = document.createElement('div');
            terminalText.appendChild(lineElem);
            
            if (lineObj.type === 'input') {
                lineElem.innerHTML = '<span class="prompt">$ </span><span class="cmd"></span><span class="cursor">_</span>';
                const cmdElem = lineElem.querySelector('.cmd');
                const cursor = lineElem.querySelector('.cursor');
                let charIndex = 0;
                
                const typingInterval = setInterval(() => {
                    if (charIndex < lineObj.text.length) {
                        cmdElem.textContent += lineObj.text.charAt(charIndex);
                        charIndex++;
                    } else {
                        clearInterval(typingInterval);
                        cursor.remove();
                        setTimeout(callback, 400); // delay before output
                    }
                }, 50); // typing speed
            } else {
                lineElem.className = lineObj.type;
                lineElem.textContent = lineObj.text;
                setTimeout(callback, 600); // delay before next line
            }
        }

        function processLines() {
            if (currentLine < lines.length) {
                typeLine(lines[currentLine], () => {
                    currentLine++;
                    processLines();
                });
            } else {
                // Append blinking cursor at the end
                const cursorElem = document.createElement('div');
                cursorElem.innerHTML = '<span class="prompt">$ </span><span class="cursor">_</span>';
                terminalText.appendChild(cursorElem);
            }
        }

        // Start terminal animation after a short delay
        setTimeout(processLines, 1000);
    }

    // Copy code button functionality
    const copyBtn = document.getElementById('copy-btn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const codeBlock = document.querySelector('.code-container code').innerText;
            navigator.clipboard.writeText(codeBlock).then(() => {
                const originalText = copyBtn.innerText;
                copyBtn.innerText = 'Copied!';
                copyBtn.style.background = 'var(--primary)';
                copyBtn.style.color = 'white';
                
                setTimeout(() => {
                    copyBtn.innerText = originalText;
                    copyBtn.style.background = '';
                    copyBtn.style.color = '';
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy text: ', err);
            });
        });
    }

    // Fetch GitHub Releases/Tags
    const releasesContainer = document.getElementById('releases-container');
    if (releasesContainer) {
        // Try fetching releases first
        fetch('https://api.github.com/repos/iammohdrazi/ProcessScope/releases')
            .then(response => response.json())
            .then(data => {
                if (Array.isArray(data) && data.length > 0) {
                    renderReleases(data);
                } else {
                    // Fallback to fetching tags if no releases exist
                    fetchTagsAsReleases();
                }
            })
            .catch(error => {
                console.error('Error fetching releases:', error);
                fetchTagsAsReleases();
            });

        function fetchTagsAsReleases() {
            fetch('https://api.github.com/repos/iammohdrazi/ProcessScope/tags')
                .then(response => response.json())
                .then(data => {
                    releasesContainer.innerHTML = '';
                    if (!Array.isArray(data) || data.length === 0) {
                        releasesContainer.innerHTML = '<div class="release-card"><p>No official releases found yet. Check back soon!</p></div>';
                        return;
                    }
                    
                    // Transform tags into mock release objects
                    const mockReleases = data.map(tag => ({
                        name: tag.name,
                        tag_name: tag.name,
                        published_at: null,
                        body: 'Release tagged as ' + tag.name,
                        html_url: `https://github.com/iammohdrazi/ProcessScope/releases/tag/${tag.name}`,
                        zipball_url: tag.zipball_url
                    }));
                    
                    renderReleases(mockReleases);
                })
                .catch(err => {
                    releasesContainer.innerHTML = '<div class="release-card"><p>Failed to load releases or tags from GitHub.</p></div>';
                    console.error('Error fetching tags:', err);
                });
        }

        function renderReleases(releases) {
            releasesContainer.innerHTML = '';
            // Show top 5
            const latest = releases.slice(0, 5);
            
            latest.forEach(release => {
                const card = document.createElement('div');
                card.className = 'release-card';
                
                const dateStr = release.published_at ? new Date(release.published_at).toLocaleDateString() : 'N/A';
                
                let assetsHtml = '';
                if (release.assets && release.assets.length > 0) {
                    assetsHtml = `<div class="release-assets">
                        ${release.assets.map(asset => `<a href="${asset.browser_download_url}" class="asset-link">⬇ ${asset.name}</a>`).join('')}
                    </div>`;
                } else {
                    assetsHtml = `<div class="release-assets">
                        <a href="${release.html_url}" target="_blank" class="asset-link">View on GitHub</a>
                        <a href="${release.zipball_url}" class="asset-link">⬇ Source Code (zip)</a>
                    </div>`;
                }
                
                const bodyText = release.body ? release.body.substring(0, 300) + (release.body.length > 300 ? '...' : '') : 'No description provided.';
                
                card.innerHTML = `
                    <div class="release-header">
                        <div class="release-version"><a href="${release.html_url}" target="_blank" style="color: inherit; text-decoration: none;">${release.name || release.tag_name}</a></div>
                        <div class="release-date">${dateStr !== 'N/A' ? dateStr : ''}</div>
                    </div>
                    <div class="release-body">${bodyText}</div>
                    ${assetsHtml}
                `;
                releasesContainer.appendChild(card);
            });
        }
    }
});
