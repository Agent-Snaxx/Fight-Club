// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { IERC3525MetadataDescriptor } from "erc-3525/contracts/periphery/interface/IERC3525MetadataDescriptor.sol";
import { Base64 } from "@openzeppelin/contracts/utils/Base64.sol";
import { Strings } from "@openzeppelin/contracts/utils/Strings.sol";

// This interface will need to match your deployed ERC-3525 agent contract
interface IAgent3525 {
    function name() external view returns (string memory);
    function valueDecimals() external view returns (uint8);
    function slotOf(uint256 tokenId) external view returns (uint256);
    function getAgentXP(uint256 tokenId) external view returns (uint256);
}

contract SnaxxMetadataDescriptor is IERC3525MetadataDescriptor {
    using Strings for uint256;

    string public constant PDF_BASE = "https://ipfs.filebase.io/ipfs/";

    // For demo, hardcode mapping tokenId/slot to file hash.
    // In production, this should be a mapping or use some dynamic assignment.
    function getPDFHash(uint256 tokenId) public pure returns (string memory) {
        if (tokenId == 1) return "QmbNg29bQpr4wC5qDoCzt8uBYKUc5U15uvuarvydLwsTMK"; // Example
        // add more cases as needed
        return "QmbNg29bQpr4wC5qDoCzt8uBYKUc5U15uvuarvydLwsTMK";
    }

    function constructContractURI() external view override returns (string memory) {
        IAgent3525 agent = IAgent3525(msg.sender);
        return string(
            abi.encodePacked(
                'data:application/json;base64,',
                Base64.encode(
                    abi.encodePacked(
                        '{"name":"', agent.name(),
                        '","description":"SNAXX Agent Ecosystem Contract",',
                        '"image":"', PDF_BASE, 'QmbNg29bQpr4wC5qDoCzt8uBYKUc5U15uvuarvydLwsTMK",',
                        '"valueDecimals":"', uint256(agent.valueDecimals()).toString(),
                        '"}'
                    )
                )
            )
        );
    }

    function constructSlotURI(uint256 slot_) external view override returns (string memory) {
        // For demo, just reference base image
        return string(
            abi.encodePacked(
                'data:application/json;base64,',
                Base64.encode(
                    abi.encodePacked(
                        '{"name":"SNAXX Slot #', slot_.toString(),
                        '","description":"A modular asset slot in the SNAXX ecosystem.",',
                        '"image":"', PDF_BASE, 'QmbNg29bQpr4wC5qDoCzt8uBYKUc5U15uvuarvydLwsTMK",',
                        '"properties":{"slotId":', slot_.toString(), '}}'
                    )
                )
            )
        );
    }

    function constructTokenURI(uint256 tokenId_) external view override returns (string memory) {
        IAgent3525 agent = IAgent3525(msg.sender);
        uint256 xp = 0;
        // If you want to wire XP, uncomment below (requires your contract to implement getAgentXP)
        // try/catch for fallback if not implemented:
        // try agent.getAgentXP(tokenId_) returns (uint256 _xp) { xp = _xp; } catch {}

        return string(
            abi.encodePacked(
                'data:application/json;base64,',
                Base64.encode(
                    abi.encodePacked(
                        '{"name":"Agent Token #', tokenId_.toString(),
                        '","description":"A SNAXX agent trading token (with dynamic XP).",',
                        '"image":"', PDF_BASE, getPDFHash(tokenId_), '",',
                        '"properties":{"xp":', xp.toString(), '}}'
                    )
                )
            )
        );
    }
}
