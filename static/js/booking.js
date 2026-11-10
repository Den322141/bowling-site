/**
 * Интерактивный калькулятор бронирования и схема зала с запросами fetch к серверному JSON API.
 * Реализует проверку вместимости дорожек (>6 гостей -> >=2 дорожек) и расчет стыка тарифов.
 */

document.addEventListener('DOMContentLoaded', function () {
  const gameSelect = document.getElementById('id_game_type');
  const dateInput = document.getElementById('id_date');
  const startSelect = document.getElementById('id_start_time');
  const endSelect = document.getElementById('id_end_time');
  const guestsInput = document.getElementById('id_guests_count');
  const cardInput = document.getElementById('id_club_card_code');
  const zonesCheckboxes = document.querySelectorAll('input[name="zones"]');

  const calcResultBox = document.getElementById('calc-summary-box');
  const warningBox = document.getElementById('calc-warning-box');

  function getSelectedZonesCount() {
    let count = 0;
    zonesCheckboxes.forEach(cb => {
      if (cb.checked) count++;
    });
    return Math.max(1, count);
  }

  function fetchPriceCalculation() {
    if (!gameSelect || !dateInput || !startSelect || !endSelect) return;

    const gameId = gameSelect.value;
    const dateVal = dateInput.value;
    const startTime = startSelect.value;
    const endTime = endSelect.value;
    const guests = guestsInput ? guestsInput.value : 2;
    const zonesCount = getSelectedZonesCount();
    const cardCode = cardInput ? cardInput.value.trim() : '';

    if (!gameId || !dateVal || !startTime || !endTime) {
      return;
    }

    const url = `/api/calculate-price/?game_type_id=${encodeURIComponent(gameId)}&date=${encodeURIComponent(dateVal)}&start_time=${encodeURIComponent(startTime)}&end_time=${encodeURIComponent(endTime)}&zones_count=${zonesCount}&guests_count=${guests}&card_code=${encodeURIComponent(cardCode)}`;

    fetch(url)
      .then(res => res.json())
      .then(data => {
        if (!data.success) {
          if (calcResultBox) {
            calcResultBox.innerHTML = `<span style="color: red;">${data.error || 'Ошибка расчета'}</span>`;
          }
          return;
        }

        // Показ предупреждения о вместимости дорожек
        if (warningBox) {
          if (data.bowling_warning) {
            warningBox.style.display = 'block';
            warningBox.innerHTML = `⚠️ <strong>Внимание:</strong> ${data.bowling_warning}`;
          } else {
            warningBox.style.display = 'none';
          }
        }

        // Индикатор стыка дневного и вечернего тарифов
        let splitBadge = '';
        if (data.day_hours > 0 && data.night_hours > 0) {
          splitBadge = `<div class="alert alert-warning" style="margin-top: 8px; padding: 6px 10px; font-size: 0.85rem;">
            🔄 <strong>Стык тарифов:</strong> Бронь пересекает дневной (до ${data.night_start}:00) и вечерний периоды. Стоимость каждого часа рассчитана по своему тарифу!
          </div>`;
        }

        let discountRow = '';
        if (data.discount_amount > 0) {
          discountRow = `<div style="color: var(--success); font-weight: 500;">
            Скидка по карте (${data.discount_percent}%): -${data.discount_amount} ₽
          </div>`;
        }

        if (calcResultBox) {
          calcResultBox.innerHTML = `
            <div style="font-size: 0.95rem;">
              <div><strong>Тип дня:</strong> ${data.day_type_display}</div>
              <div><strong>Длительность:</strong> ${data.total_hours} ч. 
                <span style="color: var(--text-muted); font-size: 0.85rem;">
                  (Дневной: ${data.day_hours} ч. × ${data.day_rate}₽ | Вечерний: ${data.night_hours} ч. × ${data.night_rate}₽)
                </span>
              </div>
              <div><strong>Выбрано зон:</strong> ${data.zones_count} шт.</div>
              ${discountRow}
              ${splitBadge}
              <div style="margin-top: 8px; font-size: 1.25rem; font-weight: bold; color: var(--primary);">
                Итого за игру: ${data.final_game_cost} ₽
              </div>
            </div>
          `;
        }
      })
      .catch(err => {
        console.error('Fetch error:', err);
      });
  }

  // Обновление доступности зон на схеме
  function updateZonesAvailability() {
    if (!dateInput || !startSelect || !endSelect) return;
    const dateVal = dateInput.value;
    const startTime = startSelect.value;
    const endTime = endSelect.value;
    const gameId = gameSelect ? gameSelect.value : '';

    if (!dateVal || !startTime || !endTime) return;

    fetch(`/api/zones-status/?date=${encodeURIComponent(dateVal)}&start_time=${encodeURIComponent(startTime)}&end_time=${encodeURIComponent(endTime)}&game_type_id=${encodeURIComponent(gameId)}`)
      .then(r => r.json())
      .then(d => {
        if (!d.success) return;
        d.zones.forEach(z => {
          const cardEl = document.getElementById(`scheme-zone-${z.id}`);
          if (cardEl) {
            cardEl.className = `lane-card ${z.status}`;
            const statusText = cardEl.querySelector('.zone-status-text');
            if (statusText) {
              statusText.textContent = (z.status === 'busy') ? 'Занято' : (z.status === 'maintenance' ? 'Ремонт' : 'Свободно');
            }
          }
        });
      })
      .catch(e => console.error('Zones fetch error:', e));
  }

  // Слушатели событий
  if (gameSelect) gameSelect.addEventListener('change', () => { fetchPriceCalculation(); updateZonesAvailability(); });
  if (dateInput) dateInput.addEventListener('change', () => { fetchPriceCalculation(); updateZonesAvailability(); });
  if (startSelect) startSelect.addEventListener('change', () => { fetchPriceCalculation(); updateZonesAvailability(); });
  if (endSelect) endSelect.addEventListener('change', () => { fetchPriceCalculation(); updateZonesAvailability(); });
  if (guestsInput) guestsInput.addEventListener('input', fetchPriceCalculation);
  if (cardInput) cardInput.addEventListener('input', fetchPriceCalculation);

  zonesCheckboxes.forEach(cb => {
    cb.addEventListener('change', fetchPriceCalculation);
  });

  // Первоначальный расчёт при загрузке страницы
  fetchPriceCalculation();
  updateZonesAvailability();
});
