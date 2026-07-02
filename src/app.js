const questionBank = {
  frontend: [
    '최근 작업한 프론트엔드 프로젝트에서 가장 어려웠던 기술적 문제와 해결 과정을 설명해 주세요.',
    'React에서 상태 관리 전략을 선택할 때 어떤 기준으로 판단하나요?',
    '웹 성능을 개선했던 경험을 구체적인 지표와 함께 설명해 주세요.',
    '접근성을 고려해 UI를 구현할 때 반드시 확인하는 항목은 무엇인가요?'
  ],
  backend: [
    '대규모 트래픽 상황에서 API 병목을 찾고 개선한 경험을 설명해 주세요.',
    '데이터베이스 인덱스를 설계할 때 고려하는 기준은 무엇인가요?',
    '장애가 발생했을 때 원인 분석과 재발 방지를 어떻게 진행하나요?',
    '동시성 문제를 해결했던 경험을 예시로 설명해 주세요.'
  ],
  product: [
    '사용자 문제를 정의하고 제품 의사결정으로 연결한 경험을 설명해 주세요.',
    '우선순위가 충돌할 때 어떤 기준으로 로드맵을 조정하나요?',
    '실패한 실험에서 무엇을 배웠고 다음 액션은 어떻게 정했나요?',
    '정성/정량 데이터를 함께 활용한 제품 개선 사례를 말해 주세요.'
  ]
};

const tips = [
  '상황, 과제, 행동, 결과를 순서대로 말하면 답변이 선명해져요.',
  '숫자나 지표를 한 가지 이상 포함하면 신뢰도가 올라가요.',
  '마지막에는 배운 점이나 다음에 다르게 할 점을 덧붙여 보세요.'
];

const state = {
  role: 'frontend',
  level: 'junior',
  index: 0,
  history: []
};

const elements = {
  roleSelect: document.querySelector('#role-select'),
  levelSelect: document.querySelector('#level-select'),
  timer: document.querySelector('#timer'),
  question: document.querySelector('#question-text'),
  tips: document.querySelector('#tips'),
  answer: document.querySelector('#answer'),
  charCount: document.querySelector('#char-count'),
  heroScore: document.querySelector('#hero-score'),
  scoreFill: document.querySelector('#score-fill'),
  scoreLabel: document.querySelector('#score-label'),
  feedbackList: document.querySelector('#feedback-list'),
  history: document.querySelector('#history'),
  nextQuestion: document.querySelector('#next-question'),
  saveAnswer: document.querySelector('#save-answer')
};

function currentQuestion() {
  const questions = questionBank[state.role];
  return questions[state.index % questions.length];
}

function scoreAnswer(answer) {
  const lengthScore = Math.min(answer.trim().length / 280, 1) * 35;
  const structureWords = ['문제', '해결', '결과', '배운', '지표', '사용자', '개선', '성과'];
  const keywordScore = structureWords.filter((word) => answer.includes(word)).length * 6;
  const specificityScore = /\d|%|명|초|분|건|배/.test(answer) ? 17 : 4;
  return Math.min(Math.round(lengthScore + keywordScore + specificityScore), 100);
}

function feedbackFor(score, answer) {
  const items = [];
  if (score >= 75) items.push('핵심 경험과 결과가 잘 드러났어요. 실제 면접에서도 설득력 있게 들릴 답변입니다.');
  else if (score >= 50) items.push('좋은 출발이에요. 행동과 결과를 조금 더 구체화하면 더 강해집니다.');
  else items.push('답변의 뼈대는 만들었어요. 상황-행동-결과 순서로 다시 정리해 보세요.');

  if (!/\d|%|명|초|분|건|배/.test(answer)) items.push('수치, 기간, 사용자 수, 개선율 같은 구체적인 지표를 하나 추가해 보세요.');
  if (!answer.includes('배운') && !answer.includes('다음')) items.push('마무리에 배운 점이나 다음 액션을 넣으면 성장 가능성이 더 잘 보입니다.');
  if (answer.trim().length < 180) items.push('답변이 다소 짧아요. 본인이 맡은 역할과 의사결정 근거를 보강해 보세요.');
  return items;
}

function renderFeedback() {
  const answer = elements.answer.value;
  const score = scoreAnswer(answer);
  elements.heroScore.textContent = `${score}점`;
  elements.scoreFill.style.width = `${score}%`;
  elements.scoreLabel.textContent = `${score} / 100`;
  elements.charCount.textContent = `${answer.length}자`;
  elements.feedbackList.innerHTML = feedbackFor(score, answer).map((item) => `<li>${item}</li>`).join('');
}

function renderQuestion() {
  elements.question.textContent = currentQuestion();
  elements.tips.innerHTML = tips.map((tip) => `<p>✅ ${tip}</p>`).join('');
}

function renderTimer() {
  const minutes = state.level === 'senior' ? '3분' : state.level === 'mid' ? '2분 30초' : '2분';
  elements.timer.textContent = `🕒 권장 답변 시간: ${minutes}`;
}

function renderHistory() {
  if (state.history.length === 0) {
    elements.history.innerHTML = '<p class="empty">아직 저장된 답변이 없습니다.</p>';
    return;
  }

  elements.history.innerHTML = state.history.map((item) => `
    <div class="history-item">
      <b>${item.score}점</b>
      <span>${item.question}</span>
    </div>
  `).join('');
}

function render() {
  renderQuestion();
  renderTimer();
  renderFeedback();
  renderHistory();
}

elements.roleSelect.addEventListener('change', (event) => {
  state.role = event.target.value;
  state.index = 0;
  elements.answer.value = '';
  render();
});

elements.levelSelect.addEventListener('change', (event) => {
  state.level = event.target.value;
  renderTimer();
});

elements.answer.addEventListener('input', renderFeedback);

elements.nextQuestion.addEventListener('click', () => {
  state.index += 1;
  elements.answer.value = '';
  render();
});

elements.saveAnswer.addEventListener('click', () => {
  const answer = elements.answer.value.trim();
  if (!answer) return;
  state.history = [{ question: currentQuestion(), score: scoreAnswer(answer) }, ...state.history].slice(0, 5);
  renderHistory();
});

render();
