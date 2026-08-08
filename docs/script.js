document.addEventListener("DOMContentLoaded", () => {
    // Typing effect for the terminal
    const terminalText = document.getElementById("terminal-text");
    
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

    // Copy code button functionality
    const copyBtn = document.getElementById('copy-btn');
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
});
