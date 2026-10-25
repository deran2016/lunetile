let count = 0;
document.querySelector('#count').onclick = event => {
  event.target.textContent = `클릭 ${++count}`;
};
