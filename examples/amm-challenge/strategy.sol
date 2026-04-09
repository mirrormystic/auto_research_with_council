// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AMMStrategyBase} from "./AMMStrategyBase.sol";
import {IAMMStrategy, TradeInfo} from "./IAMMStrategy.sol";

/// @title Strategy - EMA vol + displacement-scaled asymmetry
/// @notice Base fee from vol EMA (like 406). But asymmetric boost is
/// PROPORTIONAL to the displacement: if spot has moved far in one
/// direction, charge much more on that side (arb will hit it harder).
contract Strategy is AMMStrategyBase {

    // slots[0] = previous ratio (WAD)
    // slots[1] = EMA of ratio changes (WAD)
    // slots[2] = slow EMA of ratio itself (moving average spot price)

    uint256 constant CALM_FEE = 10 * BPS;
    uint256 constant SPIKE_FEE = 100 * BPS;
    uint256 constant VOL_ALPHA = 2e17;           // 0.2
    uint256 constant PRICE_ALPHA = 5e16;         // 0.05 — slow price tracker
    uint256 constant DISP_SCALE = 500;           // displacement multiplier for asymmetry

    function afterInitialize(uint256 initialX, uint256 initialY) external override returns (uint256, uint256) {
        uint256 ratio = wdiv(initialY, initialX);
        writeSlot(0, ratio);
        writeSlot(2, ratio); // initial slow EMA = starting ratio
        return (CALM_FEE, CALM_FEE);
    }

    function afterSwap(TradeInfo calldata trade) external override returns (uint256, uint256) {
        uint256 currentRatio = wdiv(trade.reserveY, trade.reserveX);
        uint256 prevRatio = readSlot(0);
        uint256 ratioChange = absDiff(currentRatio, prevRatio);

        // Vol EMA
        uint256 ema = readSlot(1);
        uint256 newEma = wmul(VOL_ALPHA, ratioChange) + wmul(WAD - VOL_ALPHA, ema);

        // Slow price EMA (tracks moving average of ratio/spot)
        uint256 priceEma = readSlot(2);
        uint256 newPriceEma = wmul(PRICE_ALPHA, currentRatio) + wmul(WAD - PRICE_ALPHA, priceEma);

        writeSlot(0, currentRatio);
        writeSlot(1, newEma);
        writeSlot(2, newPriceEma);

        // Base fee from vol
        uint256 volBps = wdiv(newEma, currentRatio) / BPS;
        uint256 baseFee;
        if (volBps < 5) {
            baseFee = CALM_FEE;
        } else if (volBps > 40) {
            baseFee = SPIKE_FEE;
        } else {
            uint256 range = SPIKE_FEE - CALM_FEE;
            uint256 progress = wdiv(bpsToWad(volBps - 5), bpsToWad(35));
            baseFee = CALM_FEE + wmul(progress, range);
        }

        // Displacement-scaled asymmetry
        // If current spot > EMA (price went up), arb wants to buy X → raise ask
        // If current spot < EMA (price went down), arb wants to sell X → raise bid
        uint256 bidFee = baseFee;
        uint256 askFee = baseFee;

        if (currentRatio > newPriceEma) {
            // Spot is ABOVE average → X is cheap → arb buys X (ask side)
            uint256 disp = wdiv(currentRatio - newPriceEma, newPriceEma);
            uint256 boost = disp * DISP_SCALE / WAD;
            if (boost > 30) boost = 30;
            askFee = baseFee + bpsToWad(boost);
            // Lower bid to attract retail sells
            if (baseFee > 5 * BPS) {
                bidFee = baseFee - bpsToWad(boost > 5 ? 5 : boost);
            }
        } else if (newPriceEma > currentRatio) {
            // Spot is BELOW average → X is expensive → arb sells X (bid side)
            uint256 disp = wdiv(newPriceEma - currentRatio, newPriceEma);
            uint256 boost = disp * DISP_SCALE / WAD;
            if (boost > 30) boost = 30;
            bidFee = baseFee + bpsToWad(boost);
            if (baseFee > 5 * BPS) {
                askFee = baseFee - bpsToWad(boost > 5 ? 5 : boost);
            }
        }

        return (clampFee(bidFee), clampFee(askFee));
    }

    function getName() external pure override returns (string memory) {
        return "AutoArena_v1";
    }
}
